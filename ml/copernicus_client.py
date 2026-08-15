from ml.canopy_classifier import classify_sugarcane_pixel, SCL_VALID_CLASSES
"""
IkshuVruddhi Production Copernicus CDSE Client (Strict Auditable Remote Sensing)
1. Official CDSE Process API endpoint: https://sh.dataspace.copernicus.eu/process/v1
2. Documented mosaicking order: "leastCC" (Least Cloud Coverage)
3. Strict SCL Whitelist: Only {4: Veg, 5: Bare, 6: Water}. All other classes masked to NaN.
4. Returns all computed biophysical indices: NDVI, NDRE, NDWI, LSWI, BSI, SCL, Cane Signature Score.
5. Strict metadata auditing: Explicit None when headers or userdata are absent.
"""

import os
import io
import json
import time
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional

try:
    import tifffile
    HAS_TIFFFILE = True
except ImportError:
    HAS_TIFFFILE = False

SCL_VALID_CLASSES = {4, 5, 6} # 4: Vegetation, 5: Bare Soil, 6: Water

class CopernicusCDSEProcessEngine:
    AUTH_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    PROCESS_API_URL = "https://sh.dataspace.copernicus.eu/process/v1"

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None):
        self.client_id = client_id or os.getenv("CDSE_CLIENT_ID", "")
        self.client_secret = client_secret or os.getenv("CDSE_CLIENT_SECRET", "")
        self.access_token = None
        self.token_expiry = 0

    def authenticate(self) -> Optional[str]:
        if self.access_token and time.time() < self.token_expiry - 60:
            return self.access_token

        if not self.client_id or not self.client_secret:
            return None

        try:
            payload = {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials"
            }
            resp = requests.post(self.AUTH_URL, data=payload, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.token_expiry = time.time() + data.get("expires_in", 3600)
                return self.access_token
        except Exception as e:
            print(f"[CDSE Auth Error]: {e}")
        return None

    def fetch_real_sentinel2_l2a_raster(self, polygon_coords: List[List[float]], date_str: Optional[str] = None) -> Dict[str, Any]:
        token = self.authenticate()
        
        if not token:
            return {
                "live_satellite": False,
                "status": "UNAUTHENTICATED_OFFLINE",
                "message": "CDSE_CLIENT_ID or CDSE_CLIENT_SECRET not configured. Please set environment credentials for live satellite data.",
                "product_id": None,
                "acquisition_date": None,
                "valid_cloud_free_pixels": 0,
                "cloud_pct": None,
                "cells": []
            }

        lats = [p[0] for p in polygon_coords]
        lons = [p[1] for p in polygon_coords]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        lat_step = 0.000088
        lon_step = 0.000095
        grid_height = max(int(np.ceil((max_lat - min_lat) / lat_step)), 2)
        grid_width = max(int(np.ceil((max_lon - min_lon) / lon_step)), 2)

        geojson_poly = {
            "type": "Polygon",
            "coordinates": [[ [round(pt[1], 7), round(pt[0], 7)] for pt in polygon_coords ]]
        }

        if not date_str:
            date_str = datetime.utcnow().strftime("%Y-%m-%d")

        start_date = (datetime.strptime(date_str, "%Y-%m-%d") - timedelta(days=15)).strftime("%Y-%m-%d")
        end_date = (datetime.strptime(date_str, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")

        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{
                    bands: ["B02", "B03", "B04", "B08", "B8A", "B11", "SCL"],
                    units: "DN"
                }],
                output: [
                    { id: "default", bands: 7, sampleType: "FLOAT32" }
                ]
            };
        }
        function evaluatePixel(sample) {
            return [
                sample.B02 / 10000.0,
                sample.B03 / 10000.0,
                sample.B04 / 10000.0,
                sample.B08 / 10000.0,
                sample.B8A / 10000.0,
                sample.B11 / 10000.0,
                sample.SCL
            ];
        }
        """

        payload = {
            "input": {
                "bounds": {
                    "geometry": geojson_poly
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": { "from": f"{start_date}T00:00:00Z", "to": f"{end_date}T23:59:59Z" },
                        "maxCloudCoverage": 30,
                        "mosaickingOrder": "leastCC"
                    }
                }]
            },
            "output": {
                "width": grid_width,
                "height": grid_height,
                "responses": [
                    { "identifier": "default", "format": { "type": "image/tiff" } }
                ]
            },
            "evalscript": evalscript
        }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff"
        }

        try:
            resp = requests.post(self.PROCESS_API_URL, headers=headers, json=payload, timeout=25)
            if resp.status_code == 200:
                # Authentic metadata from response headers (if present)
                acq_date = resp.headers.get("x-sentinelhub-tile-date", None)
                prod_id = resp.headers.get("x-sentinelhub-product-id", None)

                return self._parse_geotiff_response(
                    resp.content, min_lat, min_lon, lat_step, lon_step,
                    grid_height, grid_width, polygon_coords, acq_date, prod_id
                )
            else:
                return {
                    "live_satellite": False,
                    "status": "PROCESS_API_ERROR",
                    "http_status": resp.status_code,
                    "error_text": resp.text[:300],
                    "valid_cloud_free_pixels": 0,
                    "cells": []
                }
        except Exception as e:
            return {
                "live_satellite": False,
                "status": "CONNECTION_FAILED",
                "error": str(e),
                "valid_cloud_free_pixels": 0,
                "cells": []
            }

    def _parse_geotiff_response(self, tiff_bytes: bytes, min_lat: float, min_lon: float,
                                lat_step: float, lon_step: float, height: int, width: int,
                                polygon_coords: List[List[float]], acq_date: Optional[str], prod_id: Optional[str]) -> Dict[str, Any]:
        cells = []
        valid_pixel_count = 0
        invalid_pixel_count = 0

        if HAS_TIFFFILE:
            with io.BytesIO(tiff_bytes) as f:
                img_data = tifffile.imread(f)
                if img_data.ndim == 3 and img_data.shape[0] == 7:
                    img_data = np.transpose(img_data, (1, 2, 0))
        else:
            return {
                "live_satellite": False,
                "status": "MISSING_TIFF_DECODER",
                "message": "tifffile package required to decode live satellite GeoTIFF.",
                "valid_cloud_free_pixels": 0,
                "cells": []
            }

        cell_idx = 1
        for row in range(height):
            for col in range(width):
                cell_lat = min_lat + (height - 1 - row) * lat_step
                cell_lon = min_lon + col * lon_step
                cell_center = [cell_lat + lat_step / 2, cell_lon + lon_step / 2]

                b2 = float(img_data[row, col, 0])
                b3 = float(img_data[row, col, 1])
                b4 = float(img_data[row, col, 2])
                b8 = float(img_data[row, col, 3])
                b8a = float(img_data[row, col, 4])
                b11 = float(img_data[row, col, 5])
                scl = int(img_data[row, col, 6])

                is_valid = scl in SCL_VALID_CLASSES

                if not is_valid:
                    invalid_pixel_count += 1
                    ndvi = None
                    ndre = None
                    ndwi = None
                    lswi = None
                    bsi = None
                    cane_score = 0.0
                    land_class = "CLOUD_SHADOW_OR_NODATA_MASKED"
                    is_cane = False
                else:
                    valid_pixel_count += 1
                    ndvi = round(float((b8 - b4) / (b8 + b4 + 1e-7)), 3)
                    ndre = round(float((b8 - b8a) / (b8 + b8a + 1e-7)), 3)
                    ndwi = round(float((b3 - b8) / (b3 + b8 + 1e-7)), 3)
                    lswi = round(float((b8 - b11) / (b8 + b11 + 1e-7)), 3)
                    bsi = round(float(((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2) + 1e-7)), 3)

                    # Continuous Cane Signature Score calculation
                    cane_score = round(min(max(
                        0.35 * ((ndvi - 0.40) / 0.40) +
                        0.35 * ((ndre - 0.10) / 0.20) +
                        0.30 * ((lswi - 0.05) / 0.25), 0.01), 0.98), 2)

                    classification = classify_sugarcane_pixel(ndvi, ndre, lswi, ndwi, bsi, scl)
                    land_class = classification["land_class"]
                    cane_score = classification["cane_signature_score"]
                    is_cane = classification["is_standing_cane"]

                cell_poly = [
                    [cell_lat, cell_lon],
                    [cell_lat + lat_step, cell_lon],
                    [cell_lat + lat_step, cell_lon + lon_step],
                    [cell_lat, cell_lon + lon_step]
                ]

                cells.append({
                    "id": f"Cell-{cell_idx}",
                    "coords": cell_poly,
                    "center": cell_center,
                    "scl": scl,
                    "scl_valid": is_valid,
                    "ndvi": ndvi,
                    "ndre": ndre,
                    "ndwi": ndwi,
                    "lswi": lswi,
                    "bsi": bsi,
                    "land_class": land_class,
                    "is_standing_cane": is_cane,
                    "cane_signature_score": cane_score,
                    "p_cane": cane_score,
                    "bands": {
                        "B2_10m": round(b2, 4), "B3_10m": round(b3, 4), "B4_10m": round(b4, 4),
                        "B8_10m": round(b8, 4), "B8A_resampled_20m": round(b8a, 4), "B11_resampled_20m": round(b11, 4)
                    }
                })
                cell_idx += 1

        total_pixels = valid_pixel_count + invalid_pixel_count
        invalid_pct = round((invalid_pixel_count / total_pixels * 100.0), 1) if total_pixels else 0.0

        return {
            "live_satellite": True,
            "status": "LIVE_COPERNICUS_L2A",
            "source": "Copernicus Data Space Ecosystem (CDSE) Sentinel-2 L2A",
            "acquisition_date": acq_date,
            "product_id": prod_id,
            "total_pixels": total_pixels,
            "valid_cloud_free_pixels": valid_pixel_count,
            "invalid_masked_pixels": invalid_pixel_count,
            "cloud_contamination_pct": invalid_pct,
            "grid_dimensions": f"{width}x{height} (10m grid)",
            "cells": cells
        }

if __name__ == "__main__":
    engine = CopernicusCDSEProcessEngine()
    print("Copernicus CDSE Process API Engine Ready.")
