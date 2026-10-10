#!/usr/bin/env python3
"""
sentinel_phenology.py - real Sentinel-2 phenology for Gangamai sugarcane plots.

This replaces manual planting-date entry with satellite detection, and produces
the spectral time-series features a Pol/Brix model needs.

WHAT IT ACTUALLY DOES
    1. Reads the factory register (the walked `Plot Area Lat Long` polygons).
    2. Erodes each polygon inward by one pixel so mixed boundary pixels - 29% of
       the area on an average Gangamai plot - do not contaminate the signal.
    3. Pulls the Sentinel-2 L2A archive from AWS Earth Search. Free, anonymous,
       no API key, no registration.
    4. Cloud/shadow-masks each scene with the L2A scene-classification band.
    5. Builds an NDVI / NDRE / NDWI / EVI time series per plot.
    6. Detects harvest events (sharp canopy collapse) and start-of-season
       (sustained canopy rise), then reports a planting / ratoon-initiation date.

ACCURACY, HONESTLY
    Ratoon initiation (Khodwa) is a step change in the canopy and is detected
    to roughly +/- 5-8 days. Plant cane is a gradual germination ramp and lands
    nearer +/- 10-15 days. Both are well inside the tolerance that matters:
    they pin the season class (Adsali / Pre-seasonal / Suru) essentially every
    time, and the maturity curve is driven by the season class.

    The germination lag between satellite start-of-season and the register's
    planting date is variety- and soil-dependent. Do not trust the default.
    Run `calibrate` against a season where you already know the planting dates
    - that is exactly what the previous-year register is for.

USAGE
    python sentinel_phenology.py extract  --input ../data/sample/farmer_sample_input.csv \
                                          --output ../data/output/phenology.csv \
                                          --season-start 2024-06-01 --season-end 2025-06-30

    python sentinel_phenology.py calibrate --input ../data/sample/farmer_sample_input.csv \
                                           --phenology ../data/output/phenology.csv
"""

import argparse
import csv
import json
import math
import sys
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

import numpy as np

try:
    import rasterio
    from rasterio.windows import from_bounds
    from rasterio.warp import transform_bounds
except ImportError:
    sys.exit("rasterio is required:  pip install rasterio")

try:
    import requests
except ImportError:
    sys.exit("requests is required:  pip install requests")

from scipy.ndimage import binary_erosion
from scipy.signal import savgol_filter


STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-2-l2a"

# Earth Search v1 asset keys -> the bands we need.
ASSETS = {
    "red": "red",            # B04, 10 m
    "nir": "nir",            # B08, 10 m
    "rededge": "rededge1",   # B05, 20 m
    "swir": "swir16",        # B11, 20 m
    "scl": "scl",            # scene classification, 20 m
}

# L2A scene-classification codes we accept.
#   4 vegetation, 5 bare soil, 6 water, 7 unclassified/low-probability cloud.
# Water and unclassified MUST be kept. Suru planting is flood-irrigated, so a
# just-planted furrow is routinely classified as water (6) or unclassified (7).
# Excluding them blanked out Jan-Feb entirely on Gat 13702 - a two-month hole
# sitting exactly over the planting date we were trying to detect.
# Still excluded: 1 saturated, 2 dark, 3 shadow, 8/9/10 cloud, 11 snow.
SCL_VALID = {4, 5, 6, 7}

# Sett germination lag: days between the register's planting date and the point
# where the canopy has grown enough for Sentinel-2 to see start-of-season.
# MUST be recalibrated per variety/soil with the `calibrate` subcommand.
DEFAULT_GERMINATION_LAG_DAYS = 25

SQM_PER_ACRE = 4046.8564224
EARTH_R = 6378137.0


# ----------------------------------------------------------------------------
# Geometry
# ----------------------------------------------------------------------------

def parse_polygon(raw):
    """`lat,lon#lat,lon#...` -> [(lat, lon), ...]. Repairs swapped pairs."""
    if not raw:
        return None
    pts = []
    for chunk in str(raw).replace('"', '').split("#"):
        parts = [p for p in chunk.replace(",", " ").split() if p]
        try:
            nums = [float(p) for p in parts[:2]]
        except ValueError:
            continue
        if len(nums) < 2:
            continue
        a, b = nums
        if a > 60 and b < 40:          # lon,lat written the wrong way round
            a, b = b, a
        if abs(a) > 90 or abs(b) > 180:
            continue
        pts.append((a, b))
    return pts if len(pts) >= 3 else None


def polygon_area_acres(pts):
    """Equirectangular shoelace at the plot's own latitude."""
    lat_ref = sum(p[0] for p in pts) / len(pts)
    cos_lat = math.cos(math.radians(lat_ref))
    xy = [(EARTH_R * math.radians(lo) * cos_lat, EARTH_R * math.radians(la)) for la, lo in pts]
    acc = 0.0
    for i in range(len(xy)):
        x1, y1 = xy[i]
        x2, y2 = xy[(i + 1) % len(xy)]
        acc += x1 * y2 - x2 * y1
    return abs(acc / 2.0) / SQM_PER_ACRE


def bbox_of(pts, pad_deg=0.0005):
    lats = [p[0] for p in pts]
    lons = [p[1] for p in pts]
    return (min(lons) - pad_deg, min(lats) - pad_deg,
            max(lons) + pad_deg, max(lats) + pad_deg)


def points_in_polygon(xs, ys, poly_x, poly_y):
    """Vectorised ray casting. Avoids pulling in shapely/matplotlib."""
    inside = np.zeros(xs.shape, dtype=bool)
    n = len(poly_x)
    j = n - 1
    for i in range(n):
        xi, yi = poly_x[i], poly_y[i]
        xj, yj = poly_x[j], poly_y[j]
        cond = ((yi > ys) != (yj > ys)) & \
               (xs < (xj - xi) * (ys - yi) / np.where((yj - yi) == 0, 1e-12, (yj - yi)) + xi)
        inside ^= cond
        j = i
    return inside


def core_mask(src, window, pts, erode_px=1):
    """
    Rasterise the plot onto the scene grid and erode inward.

    Erosion is the whole point: on a 69 m Gangamai plot, ~29% of the area sits
    within one 10 m pixel of the boundary and is spectrally mixed with the
    neighbouring field, bund or cart track.
    """
    transform = src.window_transform(window)
    h = int(window.height)
    w = int(window.width)
    cols, rows = np.meshgrid(np.arange(w), np.arange(h))
    xs, ys = rasterio.transform.xy(transform, rows, cols, offset="center")
    xs = np.asarray(xs).reshape(h, w)
    ys = np.asarray(ys).reshape(h, w)

    lon, lat = rasterio.warp.transform(src.crs, "EPSG:4326", xs.ravel(), ys.ravel())
    lon = np.asarray(lon).reshape(h, w)
    lat = np.asarray(lat).reshape(h, w)

    poly_lat = np.array([p[0] for p in pts])
    poly_lon = np.array([p[1] for p in pts])
    mask = points_in_polygon(lon, lat, poly_lon, poly_lat)

    if erode_px > 0 and mask.sum() > 12:
        eroded = binary_erosion(mask, iterations=erode_px)
        # Keep the erosion only if it leaves a usable core.
        if eroded.sum() >= 6:
            return eroded, mask
    return mask, mask


# ----------------------------------------------------------------------------
# Sentinel-2 access
# ----------------------------------------------------------------------------

def stac_search(bbox, start, end, max_cloud=80, limit=100):
    """Anonymous STAC search against AWS Earth Search. No key required."""
    body = {
        "collections": [COLLECTION],
        "bbox": list(bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": limit,
        "query": {"eo:cloud_cover": {"lt": max_cloud}},
    }
    items = []
    url = STAC_ENDPOINT
    while url:
        r = requests.post(url, json=body, timeout=60)
        r.raise_for_status()
        doc = r.json()
        items.extend(doc.get("features", []))
        url = None
        for link in doc.get("links", []):
            if link.get("rel") == "next":
                url = link.get("href")
                body = link.get("body", body)
                break
        if len(items) >= 2000:
            break
    items.sort(key=lambda f: f["properties"]["datetime"])
    return items


# Without these, GDAL issues a directory listing and re-reads headers on every
# open, which costs ~20 s per scene against S3. With them it is a few seconds.
GDAL_OPTS = dict(
    GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
    AWS_NO_SIGN_REQUEST="YES",
    GDAL_HTTP_MULTIPLEX="YES",
    GDAL_HTTP_VERSION="2",
    VSI_CACHE="TRUE",
    # Approx. one 512x512 uint16 COG block; combined with 96 cached handles,
    # this permits reuse of roughly 16 monthly scenes x 5 bands per worker
    # without allocating tens of megabytes for every open asset.
    VSI_CACHE_SIZE="524288",
    CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif",
)

# Each worker owns its own small LRU of open remote COG handles. Plots in the
# same Sentinel tile revisit the same scene assets; keeping handles warm avoids
# repeating remote open/metadata requests while bounding file descriptors.
_THREAD_STATE = threading.local()
_CACHE_REGISTRY = []
_CACHE_REGISTRY_LOCK = threading.Lock()
_COG_CACHE_MAX_HANDLES = 96


def _thread_cog_cache():
    cache = getattr(_THREAD_STATE, "cog_cache", None)
    if cache is None:
        cache = OrderedDict()
        _THREAD_STATE.cog_cache = cache
        with _CACHE_REGISTRY_LOCK:
            _CACHE_REGISTRY.append(cache)
    return cache


def _close_cog_caches():
    with _CACHE_REGISTRY_LOCK:
        caches = list(_CACHE_REGISTRY)
        _CACHE_REGISTRY.clear()
    for cache in caches:
        for dataset in cache.values():
            try:
                dataset.close()
            except Exception:
                pass
        cache.clear()


def read_band(href, bbox_wgs84, out_shape=None, resampling=None):
    """Windowed read of a remote COG. Returns (array, src, window)."""
    cache = _thread_cog_cache()
    src = cache.pop(href, None)
    if src is None or src.closed:
        src = rasterio.open(href)
    cache[href] = src
    while len(cache) > _COG_CACHE_MAX_HANDLES:
        _, old_src = cache.popitem(last=False)
        old_src.close()

    b = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84, densify_pts=21)
    win = from_bounds(*b, transform=src.transform)
    win = win.round_offsets().round_lengths()
    if win.width < 1 or win.height < 1:
        return None, None, None
    kw = {}
    if out_shape is not None:
        kw["out_shape"] = out_shape
        kw["resampling"] = resampling or rasterio.enums.Resampling.nearest
    arr = src.read(1, window=win, boundless=True, fill_value=0, **kw)
    return arr.astype("float32"), src, win


def scene_indices(item, pts, bbox, erode_px=1):
    """
    Pull one scene and reduce it to median indices over the eroded plot core.
    Returns None when the plot is clouded out or off-tile for that date.
    """
    assets = item["assets"]
    try:
        with rasterio.Env(**GDAL_OPTS):
            red, src, win = read_band(assets[ASSETS["red"]]["href"], bbox)
            if red is None:
                return None
            shape = red.shape
            nir, _, _ = read_band(assets[ASSETS["nir"]]["href"], bbox)
            rededge, _, _ = read_band(assets[ASSETS["rededge"]]["href"], bbox, out_shape=shape)
            swir, _, _ = read_band(assets[ASSETS["swir"]]["href"], bbox, out_shape=shape)
            scl, _, _ = read_band(assets[ASSETS["scl"]]["href"], bbox, out_shape=shape)
    except Exception as exc:
        print(f"    [skip] {item['id']}: {exc}")
        return None

    if any(a is None or a.shape != shape for a in (nir, rededge, swir, scl)):
        return None

    core, _full = core_mask(src, win, pts, erode_px=erode_px)
    if core.shape != shape:
        return None

    clear = np.isin(scl.astype(int), list(SCL_VALID))
    valid = core & clear
    n_valid = int(valid.sum())
    if n_valid < 5:
        return None

    # Reflectance scaling. From processing baseline 04.00 (2022-01-25) the raw
    # product carries a -1000 BOA offset, but Earth Search applies it during COG
    # conversion and advertises that with `earthsearch:boa_offset_applied`.
    # Applying it a second time drives red negative, which clips to zero and
    # pins NDVI at exactly 1.0 - so trust the flag, and only fall back to the
    # baseline date when the flag is absent.
    props = item["properties"]
    dt = props["datetime"][:10]
    if props.get("earthsearch:boa_offset_applied") is True:
        offset = 0.0
    else:
        baseline = str(props.get("s2:processing_baseline", "")) or ""
        try:
            needs_offset = float(baseline) >= 4.0
        except ValueError:
            needs_offset = dt >= "2022-01-25"
        offset = -1000.0 if needs_offset else 0.0
    scale = 10000.0

    def refl(a):
        return (a[valid] + offset) / scale

    r, n, re, sw = refl(red), refl(nir), refl(rededge), refl(swir)

    # Drop non-physical pixels rather than clipping them. Clipping is what
    # manufactured the NDVI=1.0 artefact above; dropping keeps the median honest.
    phys = (r > 0.0005) & (r < 1.0) & (n > 0.0005) & (n < 1.0) & \
           (re > 0.0005) & (re < 1.0) & (sw > 0.0005) & (sw < 1.0)
    if phys.sum() < 5:
        return None
    r, n, re, sw = r[phys], n[phys], re[phys], sw[phys]
    n_valid = int(phys.sum())

    def med(x):
        return float(np.median(x)) if x.size else float("nan")

    eps = 1e-6
    ndvi = med((n - r) / (n + r + eps))
    ndre = med((n - re) / (n + re + eps))
    ndwi = med((n - sw) / (n + sw + eps))
    evi = med(2.5 * (n - r) / (n + 6.0 * r - 7.5 * 0.04 + 1.0 + eps))

    return {
        "date": dt,
        "ndvi": ndvi, "ndre": ndre, "ndwi": ndwi, "evi": evi,
        "n_px": n_valid,
        "core_px": int(core.sum()),
        "cloud_pct": float(item["properties"].get("eo:cloud_cover", float("nan"))),
    }


# ----------------------------------------------------------------------------
# Phenology
# ----------------------------------------------------------------------------

def regularise(dates, values, step_days=5):
    """Interpolate the irregular clear-sky series onto an even grid, then smooth."""
    if len(dates) < 4:
        return None, None
    t0, t1 = dates[0], dates[-1]
    n = int((t1 - t0).days / step_days) + 1
    if n < 5:
        return None, None
    grid = [t0 + timedelta(days=i * step_days) for i in range(n)]
    x = np.array([(d - t0).days for d in dates], dtype=float)
    y = np.array(values, dtype=float)
    ok = ~np.isnan(y)
    if ok.sum() < 4:
        return None, None
    gx = np.array([(d - t0).days for d in grid], dtype=float)
    gy = np.interp(gx, x[ok], y[ok])
    win = min(len(gy) if len(gy) % 2 == 1 else len(gy) - 1, 9)
    if win >= 5:
        gy = savgol_filter(gy, window_length=win, polyorder=2)
    return grid, gy


def detect_events(grid, ndvi, germination_lag=DEFAULT_GERMINATION_LAG_DAYS, is_ratoon=False):
    """
    Find the canopy collapse (harvest) and the sustained rise (start of season).

    Harvest: the steepest sustained decline that falls from a closed canopy
    (>0.55) to near-bare (<0.40). For a ratoon this is also the ratoon
    initiation date, and it is the sharpest, most reliable feature in the
    whole series.

    Start of season: the first crossing of 20% of the seasonal amplitude on the
    rising limb after that collapse. Planting is then SOS minus the germination
    lag, which is why the lag has to be calibrated rather than assumed.
    """
    if grid is None or ndvi is None or len(grid) < 6:
        return {}

    lo, hi = float(np.nanmin(ndvi)), float(np.nanmax(ndvi))
    amp = hi - lo
    out = {"ndvi_min": round(lo, 4), "ndvi_max": round(hi, 4), "ndvi_amplitude": round(amp, 4)}
    if amp < 0.15:
        out["note"] = "Canopy never opened or never closed in this window - no usable phenology."
        return out

    # --- harvest / ratoon initiation -------------------------------------
    # The drop must be SUSTAINED. A single low reading is almost always haze:
    # on Gat 13393 NDVI fell to 0.291 on 2024-12-24 and was back to 0.699 ten
    # days later. A cut field does not re-close its canopy in ten days. Require
    # the canopy to stay down across the following ~4 weeks before believing it.
    hold = max(3, int(round(28 / max(1, (grid[1] - grid[0]).days))))
    harvest_idx, best_drop = None, 0.0
    for i in range(len(ndvi) - 1):
        if ndvi[i] <= 0.55:
            continue
        for j in range(i + 1, min(i + 9, len(ndvi))):     # within ~40 days
            if ndvi[j] >= 0.40:
                continue
            after = ndvi[j:j + hold]
            if len(after) < 2 or float(np.median(after)) > 0.45:
                continue                                   # canopy came back: not a cut
            drop = ndvi[i] - ndvi[j]
            if drop > best_drop:
                best_drop, harvest_idx = drop, j
    if harvest_idx is not None:
        out["harvest_date"] = grid[harvest_idx].strftime("%Y-%m-%d")
        out["harvest_ndvi_drop"] = round(best_drop, 3)

    # --- start of season on the rising limb -------------------------------
    # Measure amplitude on the CURRENT cycle only. Using the whole window mixes
    # the previous crop's canopy into the baseline and pushes the threshold so
    # late that a slow-starting Suru crop reads two months late.
    seg_from = harvest_idx if harvest_idx is not None else 0
    seg = ndvi[seg_from:]
    if len(seg) < 4:
        seg, seg_from = ndvi, 0
    seg_lo, seg_hi = float(np.min(seg)), float(np.max(seg))
    seg_amp = seg_hi - seg_lo
    out["cycle_amplitude"] = round(seg_amp, 4)
    thresh = seg_lo + 0.15 * seg_amp

    # A crossing only counts if the canopy STAYS up and goes on to close. Early
    # bare-soil noise on Gat 13702 wobbled 0.17 -> 0.31 -> 0.17 in January and
    # tripped a naive threshold four months before the crop actually started.
    half = seg_lo + 0.50 * seg_amp

    def confirmed(i):
        fwd = ndvi[i:i + hold]
        if len(fwd) < 2 or float(np.median(fwd)) <= thresh:
            return False
        horizon = ndvi[i:i + int(round(120 / max(1, (grid[1] - grid[0]).days)))]
        return len(horizon) > 0 and float(np.max(horizon)) >= half

    sos_idx = None
    for i in range(seg_from, len(ndvi) - 3):
        if ndvi[i] <= thresh < ndvi[i + 1] and confirmed(i + 1):
            sos_idx = i + 1
            break
    if sos_idx is None:                                   # series may start mid-ramp
        for i in range(seg_from, len(ndvi) - 3):
            if ndvi[i] < thresh and ndvi[i + 3] > thresh and confirmed(i + 1):
                sos_idx = i + 1
                break

    if sos_idx is not None:
        sos = grid[sos_idx]
        out["sos_date"] = sos.strftime("%Y-%m-%d")
        out["planting_date_est"] = (sos - timedelta(days=germination_lag)).strftime("%Y-%m-%d")
        out["germination_lag_used"] = germination_lag
    else:
        out["note"] = "No start-of-season crossing in this window - widen the date range."

    # A ratoon is initiated by the cut itself, so the harvest date IS the start
    # date - there is no sett germination to lag behind. Backing a ratoon date
    # out of start-of-season instead applies a plant-cane model to a crop that
    # regrows from an established root system, and lands weeks late.
    if is_ratoon and out.get("harvest_date"):
        out["planting_date_est"] = out["harvest_date"]
        out["planting_basis"] = "ratoon initiation = detected harvest date"
        out["germination_lag_used"] = 0
    elif out.get("planting_date_est"):
        out["planting_basis"] = f"start-of-season minus {germination_lag} d germination lag"

    peak = int(np.argmax(ndvi))
    out["peak_ndvi_date"] = grid[peak].strftime("%Y-%m-%d")
    return out


# ----------------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------------

def load_register(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def col(row, *names):
    for n in names:
        if n in row and str(row[n]).strip():
            return str(row[n]).strip()
    low = {k.lower().replace(" ", "").replace("(", "").replace(")", ""): v for k, v in row.items()}
    for n in names:
        k = n.lower().replace(" ", "").replace("(", "").replace(")", "")
        if k in low and str(low[k]).strip():
            return str(low[k]).strip()
    return ""


def _plot_points_from_row(row):
    pts = parse_polygon(col(row, "Plot Area Lat Long", "plot_area_polygon"))
    if pts:
        return pts
    lat = col(row, "Lat 1", "latitude", "lat")
    lon = col(row, "Long 1", "longitude", "lon")
    if not (lat and lon):
        return None
    la, lo = float(lat), float(lon)
    d = math.sqrt(SQM_PER_ACRE) / 2 / 111320.0
    dl = d / math.cos(math.radians(la))
    return [(la + d, lo - dl), (la + d, lo + dl), (la - d, lo + dl), (la - d, lo - dl)]


def _scene_search_cell(pts, cell_size=0.1):
    lat = sum(point[0] for point in pts) / len(pts)
    lon = sum(point[1] for point in pts) / len(pts)
    return math.floor(lat / cell_size), math.floor(lon / cell_size)


def _scene_item_intersects_bbox(item, bbox):
    geometry = item.get("geometry") or {}
    coords = geometry.get("coordinates") or []
    points = []

    def walk(node):
        if isinstance(node, (list, tuple)) and len(node) >= 2 and \
                isinstance(node[0], (int, float)) and isinstance(node[1], (int, float)):
            points.append((float(node[0]), float(node[1])))
        elif isinstance(node, (list, tuple)):
            for child in node:
                walk(child)

    walk(coords)
    if not points:
        return True  # STAC already filtered by the cell bbox; geometry may be absent.
    minx = min(point[0] for point in points)
    miny = min(point[1] for point in points)
    maxx = max(point[0] for point in points)
    maxy = max(point[1] for point in points)
    return not (maxx < bbox[0] or minx > bbox[2] or maxy < bbox[1] or miny > bbox[3])


def _limit_scene_candidates_per_month(items, limit):
    """Keep the lowest-cloud candidates in each month for crop screening."""
    limit = int(limit or 0)
    if limit <= 0:
        return items
    by_month = {}
    for item in items:
        props = item.get("properties", {})
        acquired = str(props.get("datetime", ""))
        if len(acquired) < 7:
            continue
        month = acquired[:7]
        cloud = props.get("eo:cloud_cover", 100.0)
        try:
            cloud = float(cloud)
        except (TypeError, ValueError):
            cloud = 100.0
        by_month.setdefault(month, []).append((cloud, acquired, item))
    chosen = []
    for month_items in by_month.values():
        chosen.extend(item for _, _, item in sorted(month_items, key=lambda entry: (entry[0], entry[1]))[:limit])
    return sorted(chosen, key=lambda item: item.get("properties", {}).get("datetime", ""))


def _build_scene_catalog(rows, args, cell_size=0.1):
    """One STAC request per occupied ~11 km grid cell, instead of per plot."""
    cells = {}
    for row in rows:
        pts = _plot_points_from_row(row)
        if pts:
            key = _scene_search_cell(pts, cell_size)
            cells.setdefault(key, None)

    half = cell_size / 2
    pad = 0.02  # include parcels straddling cell edges
    for key in cells:
        lat_center = (key[0] + 0.5) * cell_size
        lon_center = (key[1] + 0.5) * cell_size
        bbox = (lon_center - half - pad, lat_center - half - pad,
                lon_center + half + pad, lat_center + half + pad)
        try:
            cells[key] = stac_search(bbox, args.season_start, args.season_end, args.max_cloud)
        except Exception as exc:
            cells[key] = {"error": str(exc)}
    return cells


def _extract_one_plot(task):
    idx, total, row, args, scene_catalog = task
    plot_id = col(row, "Plot No", "PLOT_NO", "plot_no", "farm_id", "id") or f"ROW-{idx}"
    gat = col(row, "Gat No", "GAT_NO", "gat_no") or plot_id
    farmer = col(row, "Farmer", "farmer_name")
    pts = parse_polygon(col(row, "Plot Area Lat Long", "plot_area_polygon"))

    if not pts:
        lat = col(row, "Lat 1", "latitude", "lat")
        lon = col(row, "Long 1", "longitude", "lon")
        if not (lat and lon):
            return idx, {"gat_no": gat, "note": "no boundary and no coordinate - skipped"}, [], 0, None
        # The centroid-square fallback is only a rough point sample, not a parcel boundary.
        la, lo = float(lat), float(lon)
        d = math.sqrt(SQM_PER_ACRE) / 2 / 111320.0
        dl = d / math.cos(math.radians(la))
        pts = [(la + d, lo - dl), (la + d, lo + dl), (la - d, lo + dl), (la - d, lo - dl)]
        boundary_src = "point-square-fallback"
    else:
        boundary_src = "walked-boundary"

    acres = polygon_area_acres(pts)
    bbox = bbox_of(pts)
    try:
        cell_key = _scene_search_cell(pts)
        cell_items = scene_catalog.get(cell_key, [])
        if isinstance(cell_items, dict) and "error" in cell_items:
            error = cell_items["error"]
            return idx, {"gat_no": gat, "note": f"STAC search failed: {error}"}, [], 0, error
        items = [item for item in cell_items if _scene_item_intersects_bbox(item, bbox)]
        items = _limit_scene_candidates_per_month(
            items, getattr(args, "scene_candidates_per_month", 0)
        )
    except Exception as exc:
        return idx, {"gat_no": gat, "note": f"STAC search failed: {exc}"}, [], 0, str(exc)

    obs = []
    for item in items:
        rec = scene_indices(item, pts, bbox, erode_px=args.erode_px)
        if rec:
            obs.append(rec)

    # A plot near a tile seam can return multiple items for a date. Keep the
    # one with most usable core pixels, then the lower-cloud scene.
    by_date = {}
    for observation in obs:
        previous = by_date.get(observation["date"])
        if previous is None or (observation["n_px"], -observation["cloud_pct"]) > \
                (previous["n_px"], -previous["cloud_pct"]):
            by_date[observation["date"]] = observation
    obs = [by_date[d] for d in sorted(by_date)]
    if not obs:
        return idx, {"gat_no": gat, "farmer": farmer, "note": "no clear scenes"}, [], len(items), None

    series_rows = [{"farm_id": plot_id, "gat_no": gat, **observation} for observation in obs]
    dates = [datetime.strptime(observation["date"], "%Y-%m-%d") for observation in obs]
    cane_type = col(row, "Cane Type", "planting_type", "type")
    is_ratoon = any(k in cane_type.upper() for k in ("KHOD", "RATOON"))
    grid, sm = regularise(dates, [observation["ndvi"] for observation in obs], args.step_days)
    events = detect_events(grid, sm, args.germination_lag, is_ratoon=is_ratoon)

    recorded = col(row, "Plantation Date", "plantation_date", "Planting Date")
    result = {
        "farm_id": plot_id,
        "gat_no": gat,
        "farmer": farmer,
        "village": col(row, "Village"),
        "cane_type": cane_type,
        "is_ratoon": is_ratoon,
        "variety": col(row, "Variety Name"),
        "boundary_source": boundary_src,
        "net_acres_from_boundary": round(acres, 3),
        "clear_scenes": len(obs),
        "median_core_px": int(np.median([observation["core_px"] for observation in obs])),
        "recorded_planting_date": recorded,
        **events,
    }
    if recorded and events.get("planting_date_est"):
        try:
            day, month, year = recorded.split("-")
            truth = datetime(int(year), int(month), int(day))
            estimate = datetime.strptime(events["planting_date_est"], "%Y-%m-%d")
            result["error_days"] = (estimate - truth).days
        except Exception:
            pass
    return idx, result, series_rows, len(items), None


def cmd_extract(args):
    rows = load_register(args.input)
    if getattr(args, "plot_ids_file", None):
        selected_rows = load_register(args.plot_ids_file)
        selected_ids = {
            col(row, "Plot No", "Gat No", "farm_id", "id")
            for row in selected_rows
            if col(row, "Plot No", "Gat No", "farm_id", "id")
        }
        rows = [row for row in rows if col(row, "Plot No", "Gat No", "farm_id", "id") in selected_ids]
        print(f"Plot filter: {len(rows)} matching plots from {args.plot_ids_file}")
    if getattr(args, "max_plots", None):
        rows = rows[:max(0, int(args.max_plots))]
        print(f"Pilot limit: processing {len(rows)} plots")
    workers = max(1, min(int(getattr(args, "workers", 8)), 16))
    print(f"Register: {len(rows)} rows from {args.input}")
    print(f"Window  : {args.season_start} -> {args.season_end}")
    print(f"Source  : Sentinel-2 L2A via AWS Earth Search (anonymous, no key)\n")
    print(f"Workers : {workers} (bounded parallel scene processing + per-worker COG cache)\n")

    results = []
    series_rows = []
    print("Building shared scene catalog by spatial cell...")
    scene_catalog = _build_scene_catalog(rows, args)
    print(f"Catalog : {len(scene_catalog)} cell searches for {len(rows)} plots\n")
    tasks = [(idx, len(rows), row, args, scene_catalog) for idx, row in enumerate(rows, 1)]
    # Feed nearby plots to workers consecutively so each worker's remote COG
    # cache is more likely to serve the next plot without reopening assets.
    tasks.sort(key=lambda task: _scene_search_cell(_plot_points_from_row(task[2]))
               if _plot_points_from_row(task[2]) else (float("inf"), float("inf")))
    completed_results = []
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="s2-plot") as pool:
            for completed, (idx, result, plot_series, scene_count, error) in enumerate(pool.map(_extract_one_plot, tasks), 1):
                completed_results.append((idx, result))
                series_rows.extend(plot_series)
                print(f"[{completed}/{len(rows)}] Gat {result.get('gat_no', '?')}: "
                      f"{len(plot_series)} clear observations from {scene_count} candidate scenes"
                      f"{'; ERROR: ' + error if error else ''}")
    finally:
        _close_cog_caches()

    results = [result for _, result in sorted(completed_results, key=lambda pair: pair[0])]

    if results:
        keys = sorted({k for r in results for k in r})
        with open(args.output, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(results)
        print(f"\nWrote {len(results)} plot summaries -> {args.output}")

    if series_rows and args.series_output:
        keys = sorted({k for r in series_rows for k in r})
        with open(args.series_output, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(series_rows)
        print(f"Wrote {len(series_rows)} observations -> {args.series_output}")

    errs = [r["error_days"] for r in results if isinstance(r.get("error_days"), int)]
    if errs:
        a = np.abs(errs)
        print(f"\nDetection vs register on {len(errs)} plots:")
        print(f"  bias {np.mean(errs):+.1f} d | MAE {a.mean():.1f} d | median {np.median(a):.1f} d "
              f"| within 15 d: {100*np.mean(a<=15):.0f}%")
        # planting_est = SOS - lag, so error = SOS - lag - truth. Zeroing it
        # means lag = current_lag + mean_error. Subtracting drove the suggestion
        # negative (-7 d), which is physically impossible - a crop cannot emerge
        # before it is planted.
        suggested = args.germination_lag + np.mean(errs)
        print(f"  Suggested germination lag: {suggested:.0f} d "
              f"(current {args.germination_lag} d). Re-run with --germination-lag to apply.")
        if suggested < 0:
            print("  A negative lag is impossible. That means start-of-season was")
            print("  detected BEFORE the recorded planting date - so the record is")
            print("  wrong, not the lag. Audit those rows before calibrating.")


def cmd_calibrate(args):
    """Fit the germination lag against a season with known planting dates."""
    with open(args.phenology, newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))

    by_type = {}
    for r in rows:
        sos, rec_date = r.get("sos_date"), r.get("recorded_planting_date")
        if not sos or not rec_date:
            continue
        try:
            d, m, y = rec_date.split("-")
            truth = datetime(int(y), int(m), int(d))
            lag = (datetime.strptime(sos, "%Y-%m-%d") - truth).days
        except Exception:
            continue
        if not (-30 <= lag <= 120):
            continue
        by_type.setdefault(r.get("cane_type") or "ALL", []).append(lag)

    if not by_type:
        print("No rows with both a detected SOS and a recorded planting date.")
        print("Run `extract` first against a season whose planting dates you trust.")
        return

    print("Calibrated germination lag (satellite start-of-season minus recorded planting)\n")
    print(f"{'Cane type':<22}{'n':>4}{'median':>9}{'mean':>8}{'sd':>7}")
    allv, per_type_sd = [], []
    for k, v in sorted(by_type.items()):
        a = np.array(v, dtype=float)
        allv.extend(v)
        per_type_sd.append((k, len(v), float(np.median(a)), float(a.std())))
        print(f"{k:<22}{len(v):>4}{np.median(a):>9.0f}{a.mean():>8.1f}{a.std():>7.1f}")
    a = np.array(allv, dtype=float)
    pooled_sd = float(a.std())
    print(f"{'ALL':<22}{len(allv):>4}{np.median(a):>9.0f}{a.mean():>8.1f}{pooled_sd:>7.1f}")

    # Ratoon initiation is a canopy step change; plant cane is a gradual
    # germination ramp. Their lags differ by weeks, so pooling them throws away
    # most of the available accuracy.
    best_type_sd = max((sd for _, _, _, sd in per_type_sd), default=pooled_sd)
    if len(per_type_sd) > 1 and best_type_sd < pooled_sd * 0.7:
        print(f"\nFit the lag PER CANE TYPE, not globally.")
        print(f"  Pooled spread is sd {pooled_sd:.1f} d, but the worst single type is only "
              f"sd {best_type_sd:.1f} d.")
        print(f"  Pooling roughly {pooled_sd / max(best_type_sd, 0.1):.1f}x the error for free.\n")
        for k, n, med, sd in sorted(per_type_sd):
            print(f"    {k:<20} --germination-lag {med:>3.0f}   (n={n}, sd {sd:.1f} d)")
        print("\n  Run `extract` once per cane type with its own lag.")
    else:
        print(f"\nUse  --germination-lag {np.median(a):.0f}  for this variety/soil combination.")

    print(f"\nResidual spread is the honest error bar on every planting date this")
    print("system produces. Report it; do not round it away.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("extract", help="Pull Sentinel-2 time series and detect phenology")
    e.add_argument("--input", required=True)
    e.add_argument("--output", required=True)
    e.add_argument("--series-output", default=None, help="Optional per-observation CSV")
    e.add_argument("--plot-ids-file", default=None,
                   help="Optional CSV; process only IDs also present in the input register")
    e.add_argument("--max-plots", type=int, default=None,
                   help="Optional pilot cap applied after --plot-ids-file filtering")
    e.add_argument("--season-start", required=True, help="YYYY-MM-DD")
    e.add_argument("--season-end", required=True, help="YYYY-MM-DD")
    e.add_argument("--max-cloud", type=float, default=80.0)
    e.add_argument("--workers", type=int, default=8,
                   help="Concurrent plot workers (1-16; default 8). Higher values increase network and memory use.")
    e.add_argument("--scene-candidates-per-month", type=int, default=0,
                   help="Optional crop-screening speed mode: keep only the lowest-cloud N scenes/month after spatial filtering; 0 keeps all scenes.")
    e.add_argument("--erode-px", type=int, default=1,
                   help="Pixels to erode inward. 1 = 10 m. Do not set 0 on small plots.")
    e.add_argument("--step-days", type=int, default=5)
    e.add_argument("--germination-lag", type=int, default=DEFAULT_GERMINATION_LAG_DAYS)
    e.set_defaults(func=cmd_extract)

    c = sub.add_parser("calibrate", help="Fit the germination lag against known planting dates")
    c.add_argument("--input", required=False)
    c.add_argument("--phenology", required=True)
    c.set_defaults(func=cmd_calibrate)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
