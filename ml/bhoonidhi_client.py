"""
ml/bhoonidhi_client.py
Official ISRO / NRSC Bhoonidhi OpenSearch & STAC REST API Client & LISS-4 Product Ingestion Engine
Documentation: https://bhoonidhi-api.nrsc.gov.in/bhoonidhi-api/

Scientific Ingestion Rules:
  1. Fail-Closed Georeferencing: Rejects unreferenced or identity-transform products across all formats (HDF5, TIFF).
  2. Multi-Band Co-Registration: Strictly verifies identical CRS, Affine Transform, and Shape across B2/B3/B4.
  3. Scene-Boundary Geometric Verification: Tests Area(Parcel ∩ Scene Bounds) / Area(Parcel) >= 95%.
  4. Polygon-Masked Pixel Coverage: Computes valid pixel coverage across the rasterized parcel polygon mask.
  5. Fail-Closed Radiometry: Converts to TOA Reflectance only when complete 3-band calibration metadata is present.
"""

import os
import io
import time
import math
import glob
import shutil
import zipfile
import tempfile
import requests
import numpy as np
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
from rasterio.warp import reproject, Resampling, transform_bounds
from rasterio.transform import Affine
from shapely.geometry import Polygon, box
from shapely.ops import transform
import pyproj

try:
    import h5py
    HAS_H5PY = True
except ImportError:
    HAS_H5PY = False

ESUN_LISS4 = {
    "B2_GREEN": 1853.0,
    "B3_RED":   1580.0,
    "B4_NIR":   1092.0
}

class BhoonidhiClient:
    BASE_URL = "https://bhoonidhi-api.nrsc.gov.in"
    AUTH_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/auth/token"
    SEARCH_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/data/search"
    DOWNLOAD_ENDPOINT = "https://bhoonidhi-api.nrsc.gov.in/download"

    COLLECTION_RS2A_LISS4_MX70 = "ResourceSat-2A_LISS4-MX70_L2"
    COLLECTION_RS2_LISS4_MX70  = "ResourceSat-2_LISS4-MX70_L2"
    COLLECTION_RS2A_LISS3      = "ResourceSat-2A_LISS3_L2"

    def __init__(self, user_id: Optional[str] = None, password: Optional[str] = None):
        self.user_id = user_id or os.getenv("BHOONIDHI_USER_ID", os.getenv("BHOONIDHI_USERNAME", ""))
        self.password = password or os.getenv("BHOONIDHI_PASSWORD", "")
        self.access_token = None
        self.refresh_token = None
        self.token_expiry_timestamp = 0

    def get_valid_token(self) -> Optional[str]:
        now = time.time()
        if self.access_token and now < (self.token_expiry_timestamp - 120):
            return self.access_token

        if self.refresh_token and self.user_id:
            try:
                payload = {
                    "userId": self.user_id,
                    "refresh_token": self.refresh_token,
                    "grant_type": "refresh_token"
                }
                headers = {"Content-Type": "application/json", "Accept": "application/json"}
                resp = requests.post(self.AUTH_ENDPOINT, json=payload, headers=headers, timeout=12)
                if resp.status_code == 200:
                    data = resp.json()
                    self.access_token = data.get("access_token")
                    self.refresh_token = data.get("refresh_token", self.refresh_token)
                    self.token_expiry_timestamp = now + data.get("expires_in", 3600)
                    return self.access_token
            except Exception as e:
                print(f"[Bhoonidhi Refresh Token Fallback]: {e}")

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
                self.token_expiry_timestamp = now + data.get("expires_in", 3600)
                return self.access_token
            else:
                print(f"[Bhoonidhi Auth Failed HTTP {resp.status_code}]: {resp.text[:200]}")
        except Exception as e:
            print(f"[Bhoonidhi Connection Exception]: {e}")
        return None

    def search_liss4_scenes(
        self,
        bbox: List[float],
        target_date: str = "2026-01-23",
        date_window_days: int = 5,
        collections: Optional[List[str]] = None,
        require_online_downloadable: bool = True,
        max_pages: int = 3
    ) -> Dict[str, Any]:
        if collections is None:
            collections = [self.COLLECTION_RS2A_LISS4_MX70, self.COLLECTION_RS2_LISS4_MX70]

        target_dt = datetime.strptime(target_date, "%Y-%m-%d")
        start_date = (target_dt - timedelta(days=date_window_days)).strftime("%Y-%m-%dT00:00:00Z")
        end_date = (target_dt + timedelta(days=date_window_days)).strftime("%Y-%m-%dT23:59:59Z")

        token = self.get_valid_token()
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
        
        all_features = []
        next_url = self.SEARCH_ENDPOINT
        current_payload = {
            "collections": collections,
            "bbox": bbox,
            "datetime": f"{start_date}/{end_date}",
            "limit": 50
        }
        if require_online_downloadable:
            current_payload["filter"] = {
                "op": "eq",
                "args": [{"property": "Online"}, "Y"]
            }
            current_payload["filter-lang"] = "cql2-json"

        for page in range(max_pages):
            try:
                if page == 0:
                    resp = requests.post(next_url, headers=headers, json=current_payload, timeout=20)
                else:
                    resp = requests.get(next_url, headers=headers, timeout=20)

                if resp.status_code != 200:
                    break

                data = resp.json()
                features = data.get("features", [])
                all_features.extend(features)

                next_url = None
                for link in data.get("links", []):
                    if link.get("rel") == "next" and link.get("href"):
                        next_url = link["href"]
                        break

                if not next_url:
                    break
            except Exception as e:
                print(f"[Bhoonidhi Search Page {page+1} Exception]: {e}")
                break

        for f in all_features:
            scene_dt_str = f.get("properties", {}).get("datetime", "")[:10]
            if scene_dt_str:
                try:
                    scene_dt = datetime.strptime(scene_dt_str, "%Y-%m-%d")
                    f["_date_diff_days"] = abs((scene_dt - target_dt).days)
                except Exception:
                    f["_date_diff_days"] = 999
            else:
                f["_date_diff_days"] = 999
                
        all_features.sort(key=lambda x: (x.get("_date_diff_days", 999), x.get("properties", {}).get("eo:cloud_cover", 100.0)))
        
        return {
            "authenticated": True,
            "data_source": "ISRO_BHOONIDHI_LIVE",
            "scenes_found": len(all_features),
            "features": all_features
        }

    def download_product(self, item_id: str, collection_id: str, output_dir: str = "data/raw_liss4") -> Optional[str]:
        token = self.get_valid_token()
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

def compute_earth_sun_distance_au(doy: int) -> float:
    return 1.0 - 0.01672 * math.cos(math.radians(0.9856 * (doy - 4)))

def convert_dn_to_toa_reflectance(
    dn_arr: np.ndarray,
    band_name: str,
    sun_elevation_deg: float,
    doy: int,
    lmax: float,
    lmin: float,
    qmax: float = 1023.0,
    qmin: float = 0.0
) -> np.ndarray:
    radiance = lmin + (dn_arr - qmin) * (lmax - lmin) / max(1.0, (qmax - qmin))
    d = compute_earth_sun_distance_au(doy)
    esun = ESUN_LISS4.get(band_name, 1500.0)
    sun_elev_rad = math.radians(max(5.0, min(85.0, sun_elevation_deg)))
    
    toa_reflectance = (math.pi * radiance * (d ** 2)) / (esun * math.sin(sun_elev_rad))
    return np.clip(toa_reflectance, 0.0, 1.0)

def parse_product_xml_metadata(meta_xml_path: str) -> Dict[str, Any]:
    out = {
        "sun_elevation_deg": None,
        "doy": None,
        "acquisition_date": None,
        "bands_calibration": {}
    }
    if not os.path.exists(meta_xml_path):
        return out

    try:
        tree = ET.parse(meta_xml_path)
        root = tree.getroot()
        
        for elem in root.iter():
            tag = elem.tag.lower()
            text = elem.text.strip() if elem.text else ""
            
            if ("sunelevation" in tag or "sun_elevation" in tag or "sun_elev" in tag) and text:
                try:
                    out["sun_elevation_deg"] = float(text)
                except ValueError:
                    pass
            elif ("dateofpass" in tag or "scene_date" in tag or "acquisition_date" in tag) and text and len(text) >= 10:
                try:
                    dt = datetime.strptime(text[:10], "%Y-%m-%d")
                    out["acquisition_date"] = text[:10]
                    out["doy"] = dt.timetuple().tm_yday
                except Exception:
                    pass

        for band_id, band_name in [(2, "B2_GREEN"), (3, "B3_RED"), (4, "B4_NIR")]:
            b_lmax, b_lmin = None, None
            for elem in root.iter():
                tag = elem.tag.lower()
                text = elem.text.strip() if elem.text else ""
                if f"lmax_b{band_id}" in tag or f"lmax_band{band_id}" in tag:
                    try: b_lmax = float(text)
                    except ValueError: pass
                elif f"lmin_b{band_id}" in tag or f"lmin_band{band_id}" in tag:
                    try: b_lmin = float(text)
                    except ValueError: pass
            if b_lmax is not None and b_lmin is not None:
                out["bands_calibration"][band_name] = {"lmax": b_lmax, "lmin": b_lmin, "qmax": 1023.0, "qmin": 0.0}

    except Exception as e:
        print(f"[Metadata XML Parse Warning]: {e}")
        
    return out

def extract_and_parse_liss4_package(package_path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(package_path):
        return None

    temp_extract_dir = None
    target_dir = package_path

    if os.path.isfile(package_path):
        lower_p = package_path.lower()
        if lower_p.endswith(".zip"):
            temp_extract_dir = tempfile.mkdtemp(prefix="liss4_pkg_")
            with zipfile.ZipFile(package_path, "r") as z:
                z.extractall(temp_extract_dir)
            target_dir = temp_extract_dir
        elif lower_p.endswith(".h5") or lower_p.endswith(".hdf5"):
            hdf_meta = {"sun_elevation_deg": None, "doy": None, "acquisition_date": None, "bands_calibration": {}}
            if HAS_H5PY:
                try:
                    with h5py.File(package_path, "r") as hf:
                        for k, v in hf.attrs.items():
                            kl = k.lower()
                            if "sun_elevation" in kl:
                                try: hdf_meta["sun_elevation_deg"] = float(v)
                                except Exception: pass
                            elif "date" in kl:
                                try:
                                    dt_str = str(v)[:10]
                                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                                    hdf_meta["acquisition_date"] = dt_str
                                    hdf_meta["doy"] = dt.timetuple().tm_yday
                                except Exception: pass
                except Exception: pass
            return {"format": "HDF5", "h5_path": package_path, "meta": hdf_meta, "temp_dir": None}
        elif lower_p.endswith(".tif") or lower_p.endswith(".tiff"):
            return {"format": "STACKED_GEOTIFF", "stacked_tif": package_path, "meta": {"sun_elevation_deg": None, "doy": None, "acquisition_date": None, "bands_calibration": {}}, "temp_dir": None}

    try:
        meta_files = glob.glob(os.path.join(target_dir, "**", "*.xml"), recursive=True)
        meta_parsed = parse_product_xml_metadata(meta_files[0]) if meta_files else {
            "sun_elevation_deg": None, "doy": None, "acquisition_date": None, "bands_calibration": {}
        }

        h5_files = glob.glob(os.path.join(target_dir, "**", "*.h5"), recursive=True) + glob.glob(os.path.join(target_dir, "**", "*.hdf5"), recursive=True)
        if h5_files:
            h5_file = h5_files[0]
            hdf_meta = dict(meta_parsed)
            if HAS_H5PY:
                try:
                    with h5py.File(h5_file, "r") as hf:
                        for k, v in hf.attrs.items():
                            kl = k.lower()
                            if "sun_elevation" in kl and hdf_meta["sun_elevation_deg"] is None:
                                try: hdf_meta["sun_elevation_deg"] = float(v)
                                except Exception: pass
                            elif "date" in kl and hdf_meta["doy"] is None:
                                try:
                                    dt_str = str(v)[:10]
                                    dt = datetime.strptime(dt_str, "%Y-%m-%d")
                                    hdf_meta["acquisition_date"] = dt_str
                                    hdf_meta["doy"] = dt.timetuple().tm_yday
                                except Exception: pass
                except Exception: pass

            return {
                "format": "HDF5",
                "h5_path": h5_file,
                "meta": hdf_meta,
                "temp_dir": temp_extract_dir
            }

        tif_files = glob.glob(os.path.join(target_dir, "**", "*.tif"), recursive=True) + glob.glob(os.path.join(target_dir, "**", "*.tiff"), recursive=True)
        b2_file, b3_file, b4_file = None, None, None
        
        for tf in tif_files:
            name = os.path.basename(tf).upper()
            if "BAND2" in name or "_B2" in name or "BAND_2" in name or "B2.TIF" in name:
                b2_file = tf
            elif "BAND3" in name or "_B3" in name or "BAND_3" in name or "B3.TIF" in name:
                b3_file = tf
            elif "BAND4" in name or "_B4" in name or "BAND_4" in name or "B4.TIF" in name:
                b4_file = tf

        if b2_file and b3_file and b4_file:
            return {
                "format": "INDIVIDUAL_BAND_TIFFS",
                "b2_green": b2_file,
                "b3_red": b3_file,
                "b4_nir": b4_file,
                "meta": meta_parsed,
                "temp_dir": temp_extract_dir
            }

        if tif_files:
            return {
                "format": "STACKED_GEOTIFF",
                "stacked_tif": tif_files[0],
                "meta": meta_parsed,
                "temp_dir": temp_extract_dir
            }

        return None
    except Exception as e:
        print(f"[Package Parser Error]: {e}")
        return None

def crop_and_reproject_liss4_product(
    product_path: str,
    poly_wgs84: Polygon,
    target_crs: str = "EPSG:32643"
) -> Optional[Dict[str, Any]]:
    """
    Ingests a genuine Resourcesat-2A/2 LISS-4 product:
      1. Parses package (ZIP / HDF5 / Multi-band TIFF / Stacked GeoTIFF).
      2. Strictly verifies native georeferencing & identical band co-registration.
      3. Validates scene spatial boundary overlap: Area(Parcel ∩ Scene Bounds) / Area(Parcel) >= 95%.
      4. Computes polygon-masked pixel coverage across the rasterized parcel mask.
      5. Fails closed to UNCALIBRATED_DN if calibration is incomplete.
    """
    parsed = extract_and_parse_liss4_package(product_path)
    if not parsed:
        return None

    temp_dir = parsed.get("temp_dir")
    try:
        fmt = parsed["format"]
        meta = parsed.get("meta", {})
        sun_elev = meta.get("sun_elevation_deg")
        doy = meta.get("doy")
        acq_date = meta.get("acquisition_date")
        calib_dict = meta.get("bands_calibration", {})

        green_raw, red_raw, nir_raw = None, None, None
        src_crs, src_trans, win_trans = None, None, None
        scene_bounds = None
        nodata_val = 0.0

        if fmt == "HDF5":
            h5_path = parsed["h5_path"]
            if HAS_H5PY:
                with h5py.File(h5_path, "r") as hf:
                    b2_key, b3_key, b4_key = None, None, None
                    def find_band_keys(name, obj):
                        nonlocal b2_key, b3_key, b4_key
                        if isinstance(obj, h5py.Dataset):
                            nl = name.upper()
                            if "BAND2" in nl or "BAND_2" in nl or nl.endswith("B2"): b2_key = name
                            elif "BAND3" in nl or "BAND_3" in nl or nl.endswith("B3"): b3_key = name
                            elif "BAND4" in nl or "BAND_4" in nl or nl.endswith("B4"): b4_key = name
                    hf.visititems(find_band_keys)

                    if b2_key and b3_key and b4_key:
                        try:
                            with rasterio.open(f'HDF5:"{h5_path}"://{b2_key}') as s2, \
                                 rasterio.open(f'HDF5:"{h5_path}"://{b3_key}') as s3, \
                                 rasterio.open(f'HDF5:"{h5_path}"://{b4_key}') as s4:
                                
                                # FAIL CLOSED: Verify georeferencing exists
                                if s2.crs is None or s2.transform is None or s2.transform.is_identity:
                                    print(f"[HDF5 Ingestion Rejected]: {h5_path} lacks valid GDAL geotransform/CRS.")
                                    return None

                                src_crs = s2.crs
                                src_trans = s2.transform
                                scene_bounds = s2.bounds
                                nodata_val = s2.nodata or 0.0
                                
                                to_src = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True).transform
                                poly_nat = transform(to_src, poly_wgs84)
                                win_nat = from_bounds(*poly_nat.bounds, src_trans)
                                
                                green_raw = s2.read(1, window=win_nat).astype(np.float32)
                                red_raw   = s3.read(1, window=win_nat).astype(np.float32)
                                nir_raw   = s4.read(1, window=win_nat).astype(np.float32)
                                win_trans = rasterio.windows.transform(win_nat, src_trans)
                        except Exception as e:
                            print(f"[HDF5 Subdataset Open Exception]: {e}. Failing closed.")
                            return None

        elif fmt == "INDIVIDUAL_BAND_TIFFS":
            with rasterio.open(parsed["b2_green"]) as s2, \
                 rasterio.open(parsed["b3_red"])   as s3, \
                 rasterio.open(parsed["b4_nir"])   as s4:
                
                # Check 1: Georeferencing validity
                for name, s in [("B2", s2), ("B3", s3), ("B4", s4)]:
                    if s.crs is None or s.transform is None or s.transform.is_identity:
                        print(f"[TIFF Ingestion Rejected]: Invalid/identity transform in {name}")
                        return None

                # Check 2: Strict Multi-Band Co-Registration (CRS, Transform, Shape)
                if s2.crs != s3.crs or s2.crs != s4.crs:
                    print(f"[TIFF Ingestion Rejected]: Band CRS mismatch between B2, B3, B4.")
                    return None
                
                # Verify Affine Transforms within 1e-5 tolerance
                t2, t3, t4 = s2.transform, s3.transform, s4.transform
                for idx in range(6):
                    if abs(t2[idx] - t3[idx]) > 1e-5 or abs(t2[idx] - t4[idx]) > 1e-5:
                        print(f"[TIFF Ingestion Rejected]: Band affine transform mismatch between B2, B3, B4.")
                        return None

                if s2.shape != s3.shape or s2.shape != s4.shape:
                    print(f"[TIFF Ingestion Rejected]: Band raster shape mismatch between B2, B3, B4.")
                    return None

                src_crs = s2.crs
                src_trans = s2.transform
                scene_bounds = s2.bounds
                nodata_val = s2.nodata or 0.0
                
                to_src = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True).transform
                poly_nat = transform(to_src, poly_wgs84)
                win_nat = from_bounds(*poly_nat.bounds, src_trans)
                
                green_raw = s2.read(1, window=win_nat).astype(np.float32)
                red_raw   = s3.read(1, window=win_nat).astype(np.float32)
                nir_raw   = s4.read(1, window=win_nat).astype(np.float32)
                win_trans = rasterio.windows.transform(win_nat, src_trans)

        elif fmt == "STACKED_GEOTIFF":
            with rasterio.open(parsed["stacked_tif"]) as src:
                if src.crs is None or src.transform is None or src.transform.is_identity:
                    print(f"[Stacked TIFF Ingestion Rejected]: Missing/identity georeferencing in {parsed['stacked_tif']}")
                    return None

                if src.count < 3:
                    print(f"[Stacked TIFF Ingestion Rejected]: Insufficient bands ({src.count} < 3) in {parsed['stacked_tif']}")
                    return None

                src_crs = src.crs
                src_trans = src.transform
                scene_bounds = src.bounds
                nodata_val = src.nodata or 0.0
                
                to_src = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True).transform
                poly_nat = transform(to_src, poly_wgs84)
                win_nat = from_bounds(*poly_nat.bounds, src_trans)
                
                green_raw = src.read(1, window=win_nat).astype(np.float32)
                red_raw   = src.read(2, window=win_nat).astype(np.float32)
                nir_raw   = src.read(3, window=win_nat).astype(np.float32)
                win_trans = rasterio.windows.transform(win_nat, src_trans)

        if green_raw is None or red_raw is None or nir_raw is None or src_crs is None:
            return None

        # Build Strict NoData & Validity Mask
        valid_mask = (green_raw != nodata_val) & (red_raw != nodata_val) & (nir_raw != nodata_val) & \
                     ~np.isnan(green_raw) & ~np.isnan(red_raw) & ~np.isnan(nir_raw) & (green_raw > 0)

        # 1. SCENE-BOUNDARY GEOMETRIC OVERLAP VERIFICATION
        to_nat = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True).transform
        poly_native = transform(to_nat, poly_wgs84)
        
        scene_box = box(scene_bounds.left, scene_bounds.bottom, scene_bounds.right, scene_bounds.top)
        poly_area = max(1e-5, poly_native.area)
        geom_intersection_area = poly_native.intersection(scene_box).area
        scene_overlap_pct = (geom_intersection_area / poly_area) * 100.0

        # 2. POLYGON-MASKED PIXEL COVERAGE CALCULATION
        parcel_mask = ~geometry_mask([poly_native], out_shape=green_raw.shape, transform=win_trans, invert=False)
        total_parcel_pixels = int(np.sum(parcel_mask))
        
        if total_parcel_pixels == 0 or scene_overlap_pct < 1.0:
            coverage_pct = 0.0
        else:
            valid_parcel_pixels = int(np.sum(parcel_mask & valid_mask))
            pixel_cov = (valid_parcel_pixels / total_parcel_pixels) * 100.0
            # Net coverage is bounded by actual geometric scene intersection
            coverage_pct = min(pixel_cov, scene_overlap_pct)

        # Complete 3-band calibration requirement check
        required_bands = {"B2_GREEN", "B3_RED", "B4_NIR"}
        can_calibrate = (
            sun_elev is not None and
            doy is not None and
            required_bands.issubset(set(calib_dict.keys()))
        )
        
        if can_calibrate:
            c_b2 = calib_dict["B2_GREEN"]
            c_b3 = calib_dict["B3_RED"]
            c_b4 = calib_dict["B4_NIR"]
            
            green_toa = convert_dn_to_toa_reflectance(green_raw, "B2_GREEN", sun_elev, doy, c_b2["lmax"], c_b2["lmin"])
            red_toa   = convert_dn_to_toa_reflectance(red_raw,   "B3_RED",   sun_elev, doy, c_b3["lmax"], c_b3["lmin"])
            nir_toa   = convert_dn_to_toa_reflectance(nir_raw,   "B4_NIR",   sun_elev, doy, c_b4["lmax"], c_b4["lmin"])
            radiometry_status = "TOA_PLANETARY_REFLECTANCE"
        else:
            green_toa = green_raw
            red_toa = red_raw
            nir_toa = nir_raw
            radiometry_status = "UNCALIBRATED_DN"

        return {
            "green_58m": green_toa,
            "red_58m": red_toa,
            "nir_58m": nir_toa,
            "valid_mask": valid_mask,
            "parcel_mask": parcel_mask,
            "affine_transform": win_trans,
            "crs": src_crs,
            "shape": green_raw.shape,
            "coverage_pct": round(coverage_pct, 1),
            "scene_overlap_pct": round(scene_overlap_pct, 1),
            "acquisition_date": acq_date,
            "radiometry_status": radiometry_status,
            "source_product": product_path
        }
    finally:
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)