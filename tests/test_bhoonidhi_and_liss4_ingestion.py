"""
tests/test_bhoonidhi_and_liss4_ingestion.py
Unit tests for ISRO Bhoonidhi REST Client, HDF5 Subdataset Ingestion, Fail-Closed Radiometry, and CRS Harmonization.
"""

import os
import sys
import tempfile
import numpy as np
import pytest
from unittest.mock import patch, MagicMock
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.transform import Affine

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.bhoonidhi_client import (
    BhoonidhiClient,
    extract_and_parse_liss4_package,
    crop_and_reproject_liss4_product,
    convert_dn_to_toa_reflectance,
    HAS_H5PY
)
from ml.liss4_fusion_engine import fuse_sentinel2_with_liss4_canopy

if HAS_H5PY:
    import h5py

def test_bhoonidhi_token_refresh_mocked_request():
    """Mocks requests.post and verifies that get_valid_token() sends userId, refresh_token, and grant_type."""
    client = BhoonidhiClient(user_id="test_user_isro", password="dummy_password")
    client.refresh_token = "valid_refresh_token_jwt"
    client.access_token = None
    client.token_expiry_timestamp = 0

    with patch("requests.post") as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "new_access_token_123",
            "refresh_token": "valid_refresh_token_jwt",
            "expires_in": 3600
        }
        mock_post.return_value = mock_resp

        token = client.get_valid_token()
        assert token == "new_access_token_123"
        assert mock_post.called
        call_kwargs = mock_post.call_args[1]
        sent_json = call_kwargs["json"]
        assert sent_json["userId"] == "test_user_isro"
        assert sent_json["refresh_token"] == "valid_refresh_token_jwt"
        assert sent_json["grant_type"] == "refresh_token"

def test_uncalibrated_dn_fail_closed_in_fusion():
    """Verifies that UNCALIBRATED_DN status is rejected from empirical NDVI fusion."""
    poly_utm = Polygon([(500000, 2130000), (500100, 2130000), (500100, 2130100), (500000, 2130100)])
    s2_arr = np.full((10, 10), 0.6, dtype=np.float32)
    s2_trans = Affine(10.0, 0, 500000, 0, -10.0, 2130100)
    
    # Real LISS-4 arrays provided but radiometry_status is UNCALIBRATED_DN
    liss4_arr = np.full((18, 18), 500.0, dtype=np.float32)
    liss4_trans = Affine(5.8, 0, 500000, 0, -5.8, 2130100)
    
    out = fuse_sentinel2_with_liss4_canopy(
        poly_utm=poly_utm,
        s2_red_10m=s2_arr * 0.1,
        s2_nir_10m=s2_arr * 0.8,
        s2_re_10m=s2_arr * 0.4,
        s2_swir_10m=s2_arr * 0.2,
        s2_scl_10m=np.full((10, 10), 4, dtype=np.uint8),
        s2_transform=s2_trans,
        liss4_green_58m=liss4_arr,
        liss4_red_58m=liss4_arr,
        liss4_nir_58m=liss4_arr,
        liss4_transform=liss4_trans,
        liss4_crs="EPSG:32643",
        radiometry_status="UNCALIBRATED_DN"
    )
    assert out["data_source"] == "EMPIRICAL_ISRO_LISS4_REJECTED"
    assert out["fused_liss4"] is None
    assert "rejected" in out["message"].lower()

@pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed")
def test_hdf5_raster_subdataset_ingestion():
    """Verifies that crop_and_reproject_liss4_product reads actual raster arrays from HDF5."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "RS2A_L4_raster_product.h5")
        
        with h5py.File(h5_path, "w") as hf:
            hf.attrs["SUN_ELEVATION"] = 45.0
            hf.attrs["DATE_OF_PASS"] = "2026-01-24"
            hf.create_dataset("Band2", data=np.full((50, 50), 200, dtype=np.uint16))
            hf.create_dataset("Band3", data=np.full((50, 50), 300, dtype=np.uint16))
            hf.create_dataset("Band4", data=np.full((50, 50), 600, dtype=np.uint16))
            
        poly_wgs = Polygon([(75.000, 19.305), (75.003, 19.305), (75.003, 19.308), (75.000, 19.308)])
        res = crop_and_reproject_liss4_product(h5_path, poly_wgs)
        assert res is not None
        assert res["green_58m"].shape == (50, 50)
        assert res["green_58m"][0, 0] == 200.0

def test_different_crs_reprojection_in_fusion():
    """Verifies that when LISS-4 has a different CRS, fusion reprojects to UTM Zone 43N properly."""
    wgs_to_utm = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform
    poly_wgs = Polygon([(75.001, 19.305), (75.002, 19.305), (75.002, 19.306), (75.001, 19.306)])
    poly_utm = transform(wgs_to_utm, poly_wgs)
    minx, miny, maxx, maxy = poly_utm.bounds
    
    s2_arr = np.full((10, 10), 0.6, dtype=np.float32)
    s2_trans = Affine(10.0, 0, minx, 0, -10.0, maxy)
    
    # LISS-4 raster covering this WGS84 bounding box in EPSG:4326
    liss4_arr = np.full((50, 50), 0.7, dtype=np.float32)
    liss4_trans = Affine(0.00005, 0, 75.000, 0, -0.00005, 19.308)
    
    out = fuse_sentinel2_with_liss4_canopy(
        poly_utm=poly_utm,
        s2_red_10m=s2_arr * 0.1,
        s2_nir_10m=s2_arr * 0.8,
        s2_re_10m=s2_arr * 0.4,
        s2_swir_10m=s2_arr * 0.2,
        s2_scl_10m=np.full((10, 10), 4, dtype=np.uint8),
        s2_transform=s2_trans,
        liss4_green_58m=liss4_arr * 0.3,
        liss4_red_58m=liss4_arr * 0.1,
        liss4_nir_58m=liss4_arr * 0.8,
        liss4_transform=liss4_trans,
        liss4_crs="EPSG:4326",
        radiometry_status="TOA_PLANETARY_REFLECTANCE"
    )
    assert out["data_source"] == "EMPIRICAL_ISRO_LISS4"
    assert out["fused_liss4"] is not None
    assert out["fused_liss4"]["fused_occupancy_pct"] > 0

if __name__ == "__main__":
    pytest.main(["-v", __file__])