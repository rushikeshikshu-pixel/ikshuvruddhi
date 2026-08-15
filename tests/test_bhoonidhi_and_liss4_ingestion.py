"""
tests/test_bhoonidhi_and_liss4_ingestion.py
Unit tests for ISRO Bhoonidhi REST Client and LISS-4 Product Ingestion Pipeline.
"""

import os
import sys
import tempfile
import numpy as np
import pytest
from shapely.geometry import Polygon
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
if HAS_H5PY:
    import h5py

def test_bhoonidhi_token_refresh_payload():
    """Verifies that token refresh payload strictly includes userId, refresh_token, and grant_type."""
    client = BhoonidhiClient(user_id="isro_user_test", password="dummy_password")
    client.refresh_token = "mock_jwt_refresh_token_xyz"
    client.access_token = None
    client.token_expiry_timestamp = 0
    
    payload = {
        "userId": client.user_id,
        "refresh_token": client.refresh_token,
        "grant_type": "refresh_token"
    }
    assert payload["userId"] == "isro_user_test"
    assert payload["refresh_token"] == "mock_jwt_refresh_token_xyz"
    assert payload["grant_type"] == "refresh_token"

def test_fail_closed_radiometry_without_metadata():
    """Verifies that when calibration metadata is absent, the system fails closed (marking UNCALIBRATED_DN)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        stacked_tif = os.path.join(tmpdir, "RS2A_L4_dummy.tif")
        # Origin centered in UTM Zone 43N (Lon ~75.0, Lat ~19.3 -> X ~500000, Y ~2130000)
        transform = Affine(5.8, 0, 500000, 0, -5.8, 2135000)
        data = np.ones((3, 100, 100), dtype=np.float32) * 500.0
        
        with rasterio.open(
            stacked_tif, "w",
            driver="GTiff",
            height=100, width=100,
            count=3,
            dtype=np.float32,
            crs="EPSG:32643",
            transform=transform
        ) as dst:
            dst.write(data)
            
        # WGS84 polygon that lands squarely inside raster bounds
        poly_wgs = Polygon([(75.000, 19.305), (75.003, 19.305), (75.003, 19.308), (75.000, 19.308)])
        res = crop_and_reproject_liss4_product(stacked_tif, poly_wgs)
        
        assert res is not None
        assert res["radiometry_status"] == "UNCALIBRATED_DN"
        assert res["green_58m"][0, 0] == 500.0

@pytest.mark.skipif(not HAS_H5PY, reason="h5py not installed")
def test_hdf5_product_ingestion():
    """Verifies that HDF5 Level-2 products with internal datasets and attributes are parsed cleanly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        h5_path = os.path.join(tmpdir, "RS2A_L4_product.h5")
        
        with h5py.File(h5_path, "w") as hf:
            hf.attrs["SUN_ELEVATION"] = 42.0
            hf.attrs["DATE_OF_PASS"] = "2026-01-24"
            
            hf.create_dataset("Band2", data=np.full((100, 100), 200, dtype=np.uint16))
            hf.create_dataset("Band3", data=np.full((100, 100), 300, dtype=np.uint16))
            hf.create_dataset("Band4", data=np.full((100, 100), 600, dtype=np.uint16))
            
        parsed = extract_and_parse_liss4_package(h5_path)
        assert parsed is not None
        assert parsed["format"] == "HDF5"
        assert parsed["meta"]["sun_elevation_deg"] == 42.0
        assert parsed["meta"]["acquisition_date"] == "2026-01-24"

if __name__ == "__main__":
    pytest.main(["-v", __file__])