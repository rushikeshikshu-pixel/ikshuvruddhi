"""
ml/bhoonidhi_client.py
Official ISRO / NRSC Bhoonidhi OpenSearch & STAC REST API Client
Reference Documentation: https://bhoonidhi.nrsc.gov.in/bhoonidhi-api/

Official API Specifications:
  1. Base URL: https://bhoonidhi-api.nrsc.gov.in
  2. Authentication Endpoint: POST https://bhoonidhi-api.nrsc.gov.in/auth/token
     Payload: {"userId": "<user_id>", "password": "<password>", "grant_type": "password"}
     Returns: {"access_token": "<jwt>", "refresh_token": "<jwt>", "expires_in": 3600}
  3. STAC / OpenSearch Endpoint: POST/GET https://bhoonidhi-api.nrsc.gov.in/data/search
     STAC Payload: {
       "collections": ["ResourceSat-2A_LISS4-MX70_L2", "ResourceSat-2_LISS4-MX70_L2"],
       "bbox": [min_lon, min_lat, max_lon, max_lat],
       "datetime": "2026-01-18T00:00:00Z/2026-01-28T23:59:59Z",
       "limit": 50
     }
  4. Product Download Endpoint: GET https://bhoonidhi-api.nrsc.gov.in/download?id=<item_id>&collection=<collection_id>
  5. Static IP Whitelisting: Requires client static IPv4 registered with NRSC.
"""

import os
import io
import json
import zipfile
import tempfile
import requests
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling, transform_bounds
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj

class BhoonidhiClient:
    """
    Official ISRO Bhoonidhi REST Client implementing the exact NRSC Bhoonidhi-API spec.
    """
    BASE_URL = "https://bhoonidhi-api.nrsc.gov.in"
    AUTH_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/auth/token"
    SEARCH_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/data/search"
    DOWNLOAD_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/download"

    # Official Bhoonidhi Collection Identifiers
    COLLECTION_RS2A_LISS4_MX70 = "ResourceSat-2A_LISS4-MX70_L2"
    COLLECTION_RS2_LISS4_MX70  = "ResourceSat-2_LISS4-MX70_L2"
    COLLECTION_RS2A_LISS3      = "ResourceSat-2A_LISS3_L2"

    def __init__(self, user_id: Optional[str] = None, password: Optional[str] = None):
        self.user_id = user_id or os.getenv("BHOONIDHI_USER_ID", os.getenv("BHOONIDHI_USERNAME", ""))
        self.password = password or os.getenv("BHOONIDHI_PASSWORD", "")
        self.access_token = None
        self.refresh_token = None
        self.token_expiry = 0

    def authenticate(self) -> Optional[str]:
        """
        Authenticates with official Bhoonidhi JSON grant_type payload.
        """
        if not self.user_id or not self.password:
            return None

        try:
            payload = {
                "userId": self.user_id,
                "password": self.password,
                "grant_type": "password"
            }
            headers = {"Content-Type": "application/json", "Accept": "application/json"}
            resp = requests.post(self.AUTH_ENDPOINT, json=payload, headers=headers, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("access_token")
                self.refresh_token = data.get("refresh_token")
                self.token_expiry = data.get("expires_in", 3600)
                return self.access_token
            else:
                print(f"[Bhoonidhi Auth Failed HTTP {resp.status_code}]: {resp.text[:200]}")
        except Exception as e:
            print(f"[Bhoonidhi Connection Error]: {e}")
        return None

    def search_liss4_scenes(
        self,
        bbox: List[float], # [min_lon, min_lat, max_lon, max_lat]
        target_date: str = "2026-01-23",
        date_window_days: int = 5,
        max_cloud_cover: float = 15.0,
        collections: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes official STAC search for Resourcesat-2A/2 LISS-4 scenes.
        """
        if collections is None:
            collections = [self.COLLECTION_RS2A_LISS4_MX70, self.COLLECTION_RS2_LISS4_MX70]

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date = (target_dt - timedelta(days=date_window_days)).strftime("%Y-%m-%dT00:00:00Z")
        end_date = (target_dt + timedelta(days=date_window_days)).strftime("%Y-%m-%dT23:59:59Z")

        token = self.authenticate()
        if not token:
            return {
                "authenticated": False,
                "data_source": "BHOONIDHI_UNAUTHENTICATED",
                "message": "BHOONIDHI_USER_ID & BHOONIDHI_PASSWORD not configured (or static IP not whitelisted by NRSC).",
                "target_bbox": bbox,
                "target_datetime_range": f"{start_date}/{end_date}",
                "collections_queried": collections,
                "scenes_found": 0,
                "features": []
            }

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        stac_payload = {
            "collections": collections,
            "bbox": bbox,
            "datetime": f"{start_date}/{end_date}",
            "query": {
                "eo:cloud_cover": {"lte": max_cloud_cover}
            },
            "limit": 50
        }

        try:
            resp = requests.post(self.SEARCH_ENDPOINT, headers=headers, json=stac_payload, timeout=20)
            if resp.status_code == 200:
                data = resp.json()
                features = data.get("features", [])
                
                # Rank results by proximity to target date and minimum cloud cover
                for f in features:
                    scene_dt_str = f.get("properties", {}).get("datetime", "")[:10]
                    if scene_dt_str:
                        scene_dt = datetime.strptime(scene_dt_str, "%Y-%m-%d")
                        f["_date_diff_days"] = abs((scene_dt - target_dt).days)
                    else:
                        f["_date_diff_days"] = 999
                        
                features.sort(key=lambda x: (x.get("_date_diff_days", 999), x.get("properties", {}).get("eo:cloud_cover", 100.0)))
                
                return {
                    "authenticated": True,
                    "data_source": "ISRO_BHOONIDHI_LIVE",
                    "scenes_found": len(features),
                    "features": features
                }
            else:
                return {
                    "authenticated": True,
                    "data_source": "BHOONIDHI_SEARCH_ERROR",
                    "http_status": resp.status_code,
                    "error": resp.text[:300],
                    "scenes_found": 0,
                    "features": []
                }
        except Exception as e:
            return {
                "authenticated": False,
                "data_source": "BHOONIDHI_EXCEPTION",
                "error": str(e),
                "scenes_found": 0,
                "features": []
            }

    def download_product(self, item_id: str, collection_id: str, output_dir: str = "data/raw_liss4") -> Optional[str]:
        """
        Downloads a product ZIP/GeoTIFF package via official /download endpoint.
        """
        token = self.authenticate()
        if not token:
            print("[Bhoonidhi Download Error]: Unauthenticated.")
            return None

        headers = {"Authorization": f"Bearer {token}"}
        params = {"id": item_id, "collection": collection_id}
        
        try:
            os.makedirs(output_dir, exist_ok=True)
            out_file = os.path.join(output_dir, f"{item_id}.zip")
            
            with requests.get(self.DOWNLOAD_ENDPOINT, headers=headers, params=params, stream=True, timeout=60) as r:
                if r.status_code == 200:
                    with open(out_file, "wb") as f:
                        for chunk in r.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                f.write(chunk)
                    print(f"[Bhoonidhi Download Success]: {out_file}")
                    return out_file
                else:
                    print(f"[Bhoonidhi Download Failed HTTP {r.status_code}]: {r.text[:200]}")
        except Exception as e:
            print(f"[Bhoonidhi Download Exception]: {e}")
        return None

def crop_and_reproject_liss4_geotiff(
    liss4_geotiff_path: str,
    poly_wgs84: Polygon,
    target_crs: str = "EPSG:32643",
    target_res: float = 5.8
) -> Optional[Dict[str, Any]]:
    """
    Ingests a genuine Resourcesat-2A LISS-4 GeoTIFF product:
      1. Reads native raster CRS, Affine Transform, and multi-band data (B2 Green, B3 Red, B4 NIR).
      2. Transforms parcel polygon into native raster CRS.
      3. Extracts tight raster window around parcel.
      4. Reprojects to EPSG:32643 UTM Zone 43N at exact 5.8m ground sampling distance.
      5. Returns scaled surface reflectance arrays (0.0 to 1.0) and exact target affine transform.
    """
    if not os.path.exists(liss4_geotiff_path):
        return None

    try:
        with rasterio.open(liss4_geotiff_path) as src:
            src_crs = src.crs
            
            # Reproject WGS84 polygon to native LISS-4 CRS
            to_src_crs = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True).transform
            poly_native = transform(to_src_crs, poly_wgs84)
            minx_nat, miny_nat, maxx_nat, maxy_nat = poly_native.bounds
            
            # Read native raster window
            win = from_bounds(minx_nat, miny_nat, maxx_nat, maxy_nat, src.transform)
            
            # Read bands (LISS-4 standard 3-band VNIR: 1: Green, 2: Red, 3: NIR)
            green_raw = src.read(1, window=win).astype(np.float32)
            red_raw   = src.read(2, window=win).astype(np.float32)
            nir_raw   = src.read(3, window=win).astype(np.float32)
            
            # Transform polygon to target UTM 43N (EPSG:32643)
            to_utm = pyproj.Transformer.from_crs("EPSG:4326", target_crs, always_xy=True).transform
            poly_utm = transform(to_utm, poly_wgs84)
            minx, miny, maxx, maxy = poly_utm.bounds
            
            # Calculate target 5.8m grid dimensions
            width_58m = max(int(np.ceil((maxx - minx) / target_res)), 2)
            height_58m = max(int(np.ceil((maxy - miny) / target_res)), 2)
            target_trans = rasterio.transform.from_bounds(minx, miny, maxx, maxy, width_58m, height_58m)
            
            # Reproject each band onto target UTM 5.8m affine grid (Bilinear)
            green_58m = np.zeros((height_58m, width_58m), dtype=np.float32)
            red_58m   = np.zeros((height_58m, width_58m), dtype=np.float32)
            nir_58m   = np.zeros((height_58m, width_58m), dtype=np.float32)
            
            win_transform = rasterio.windows.transform(win, src.transform)
            
            reproject(source=green_raw, destination=green_58m, src_transform=win_transform, src_crs=src_crs, dst_transform=target_trans, dst_crs=target_crs, resampling=Resampling.bilinear)
            reproject(source=red_raw, destination=red_58m, src_transform=win_transform, src_crs=src_crs, dst_transform=target_trans, dst_crs=target_crs, resampling=Resampling.bilinear)
            reproject(source=nir_raw, destination=nir_58m, src_transform=win_transform, src_crs=src_crs, dst_transform=target_trans, dst_crs=target_crs, resampling=Resampling.bilinear)
            
            # Radiometric scaling (10-bit or DN to reflectance 0.0 - 1.0)
            max_val = max(np.max(nir_58m), 1.0)
            scale = 1.0 / 1023.0 if max_val <= 1024 else 1.0 / 10000.0 if max_val > 1024 else 1.0
            
            return {
                "green_58m": green_58m * scale,
                "red_58m": red_58m * scale,
                "nir_58m": nir_58m * scale,
                "affine_transform": target_trans,
                "shape": (height_58m, width_58m),
                "crs": target_crs,
                "source_file": liss4_geotiff_path
            }
    except Exception as e:
        print(f"[LISS-4 Ingestion Error]: {e}")
        return None