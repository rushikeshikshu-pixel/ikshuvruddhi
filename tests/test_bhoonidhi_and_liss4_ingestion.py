"""
tests/test_bhoonidhi_and_liss4_ingestion.py
Comprehensive unit tests for ISRO Bhoonidhi REST Client, Fail-Closed Georeferencing,
Scene-Boundary Geometric Verification, Multi-Band Alignment, and Fail-Closed Radiometry.
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

def test_exact_polygon_specific_coverage_calculation():
    """Verifies that coverage is calculated strictly over the rasterized parcel polygon mask."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tif_path = os.path.join(tmpdir, "test_coverage.tif")
        transform_affine = Affine(5.8, 0, 500000, 0, -5.8, 2135000)
        
        arr = np.zeros((3, 100, 100), dtype=np.float32)
        arr[:, :, :50] = 500.0 # Left half valid, right half nodata
        
        with rasterio.open(
            tif_path, "w",
            driver="GTiff",
            height=100, width=100,
            count=3,
            dtype=np.float32,
            crs="EPSG:32643",
            transform=transform_affine,
            nodata=0.0
        ) as dst:
            dst.write(arr)
            
        to_wgs = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform
        poly_utm_a = Polygon([(500050, 2134800), (500200, 2134800), (500200, 2134950), (500050, 2134950)])
        poly_wgs_a = transform(to_wgs, poly_utm_a)
        
        res_a = crop_and_reproject_liss4_product(tif_path, poly_wgs_a)
        assert res_a is not None
        assert res_a["coverage_pct"] >= 99.0

        poly_utm_b = Polygon([(500200, 2134800), (500400, 2134800), (500400, 2134950), (500200, 2134950)])
        poly_wgs_b = transform(to_wgs, poly_utm_b)
        
        res_b = crop_and_reproject_liss4_product(tif_path, poly_wgs_b)
        assert res_b is not None
        assert 40.0 <= res_b["coverage_pct"] <= 55.0

def test_parcel_partially_outside_scene_boundary():
    """Verifies that when a parcel crosses the outer satellite scene boundary, coverage falls proportionally."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tif_path = os.path.join(tmpdir, "scene_edge.tif")
        # 100x100 raster starting at X=500000, Y=2135000 (X max = 500580)
        transform_affine = Affine(5.8, 0, 500000, 0, -5.8, 2135000)
        arr = np.full((3, 100, 100), 500.0, dtype=np.float32) # All pixels valid inside scene
        
        with rasterio.open(
            tif_path, "w",
            driver="GTiff",
            height=100, width=100,
            count=3,
            dtype=np.float32,
            crs="EPSG:32643",
            transform=transform_affine,
            nodata=0.0
        ) as dst:
            dst.write(arr)
            
        to_wgs = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform
        # Polygon spanning from X=500480 to 500680 (100m inside, 100m outside scene)
        poly_utm_outside = Polygon([(500480, 2134800), (500680, 2134800), (500680, 2134950), (500480, 2134950)])
        poly_wgs_outside = transform(to_wgs, poly_utm_outside)
        
        res = crop_and_reproject_liss4_product(tif_path, poly_wgs_outside)
        assert res is not None
        assert res["scene_overlap_pct"] <= 60.0
        assert res["coverage_pct"] <= 60.0 # Bounded by geometric intersection

def test_band_alignment_mismatch_rejection():
    """Verifies that individual band TIFFs with mismatched affine transforms are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        b2_path = os.path.join(tmpdir, "BAND2.tif")
        b3_path = os.path.join(tmpdir, "BAND3.tif")
        b4_path = os.path.join(tmpdir, "BAND4.tif")
        
        t_b2 = Affine(5.8, 0, 500000, 0, -5.8, 2135000)
        t_b3_shifted = Affine(5.8, 0, 500050, 0, -5.8, 2135000) # 50m shift!
        
        arr = np.full((1, 50, 50), 400.0, dtype=np.float32)
        
        for p, trans in [(b2_path, t_b2), (b3_path, t_b3_shifted), (b4_path, t_b2)]:
            with rasterio.open(p, "w", driver="GTiff", height=50, width=50, count=1, dtype=np.float32, crs="EPSG:32643", transform=trans) as dst:
                dst.write(arr)
                
        to_wgs = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform
        poly_utm = Polygon([(500050, 2134800), (500150, 2134800), (500150, 2134900), (500050, 2134900)])
        poly_wgs = transform(to_wgs, poly_utm)
        
        # Ingestion of multi-file directory must fail closed
        res = crop_and_reproject_liss4_product(tmpdir, poly_wgs)
        assert res is None

def test_identity_transform_geotiff_rejection():
    """Verifies that GeoTIFFs with identity transforms are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tif_path = os.path.join(tmpdir, "identity_trans.tif")
        arr = np.full((3, 50, 50), 500.0, dtype=np.float32)
        
        with rasterio.open(
            tif_path, "w", driver="GTiff", height=50, width=50, count=3, dtype=np.float32, crs="EPSG:32643", transform=Affine.identity()
        ) as dst:
            dst.write(arr)
            
        poly_wgs = Polygon([(75.001, 19.305), (75.002, 19.305), (75.002, 19.306), (75.001, 19.306)])
        res = crop_and_reproject_liss4_product(tif_path, poly_wgs)
        assert res is None

def test_stacked_geotiff_insufficient_bands_rejection():
    """Verifies that stacked GeoTIFFs with fewer than 3 bands are rejected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tif_path = os.path.join(tmpdir, "two_bands.tif")
        arr = np.full((2, 50, 50), 500.0, dtype=np.float32) # Only 2 bands
        trans = Affine(5.8, 0, 500000, 0, -5.8, 2135000)
        
        with rasterio.open(
            tif_path, "w", driver="GTiff", height=50, width=50, count=2, dtype=np.float32, crs="EPSG:32643", transform=trans
        ) as dst:
            dst.write(arr)
            
        poly_wgs = Polygon([(75.001, 19.305), (75.002, 19.305), (75.002, 19.306), (75.001, 19.306)])
        res = crop_and_reproject_liss4_product(tif_path, poly_wgs)
        assert res is None

@pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed")
def test_fail_closed_on_unreferenced_hdf5():
    """Verifies that an HDF5 dataset without valid geotransform/CRS is rejected (fails closed)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "unreferenced.h5")
        with h5py.File(h5_path, "w") as hf:
            hf.create_dataset("Band2", data=np.full((50, 50), 200, dtype=np.uint16))
            hf.create_dataset("Band3", data=np.full((50, 50), 300, dtype=np.uint16))
            hf.create_dataset("Band4", data=np.full((50, 50), 600, dtype=np.uint16))
            
        poly_wgs = Polygon([(75.000, 19.305), (75.003, 19.305), (75.003, 19.308), (75.000, 19.308)])
        res = crop_and_reproject_liss4_product(h5_path, poly_wgs)
        assert res is None

def test_uncalibrated_dn_fail_closed_in_fusion():
    """Verifies that UNCALIBRATED_DN status is rejected from empirical NDVI fusion."""
    poly_utm = Polygon([(500000, 2130000), (500100, 2130000), (500100, 2130100), (500000, 2130100)])
    s2_arr = np.full((10, 10), 0.6, dtype=np.float32)
    s2_trans = Affine(10.0, 0, 500000, 0, -10.0, 2130100)
    
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

if __name__ == "__main__":
    pytest.main(["-v", __file__])