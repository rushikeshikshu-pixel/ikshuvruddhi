"""
validation/run_spatio_temporal_audit.py
High-Speed Empirical Spatio-Temporal Audit across 320 Registered Mill Parcels.
Uses Tile-Specific BBox Envelope Memory Caching with Cleanest Scene Selection.
"""

import os
import sys
import time
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.ops import transform, unary_union
import pyproj
import rasterio

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.sentinel_timeseries_harvester import rank_scene_quality, TileSceneMemoryCache
from ml.phenology_features import extract_phenological_trajectory_features
from ml.spatio_temporal_engine import evaluate_spatio_temporal_profile, detect_canopy_collapse_events

wgs84_to_utm43n = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform

def run_empirical_spatio_temporal_audit(
    spatial_csv: str = "data/output/spatial_context_audit_320plots.csv",
    output_csv: str = "data/output/spatio_temporal_audit_320plots.csv",
    output_54_csv: str = "data/output/spatio_temporal_54_low_canopy_audit.csv"
):
    start_time = time.time()
    print("==================================================================")
    print(" IKSHU HIGH-SPEED EMPIRICAL SPATIO-TEMPORAL AUDIT (320 PARCELS)")
    print(f" Source: {spatial_csv} | Output: {output_csv}")
    print(" Engine: Per-Tile BBox Envelope Memory Caching (Cleanest STAC Scenes)")
    print("==================================================================")

    df_spatial = pd.read_csv(os.path.join(REPO_ROOT, spatial_csv))
    print(f"Loaded {len(df_spatial)} registered parcel records.")

    # Load polygon geometries
    src_csv = os.path.join(REPO_ROOT, "data", "sugarcane_adsali_season_2627.csv")
    df_raw = pd.read_csv(src_csv)
    poly_dict = {}
    for _, raw_r in df_raw.iterrows():
        p_no = str(raw_r["Plot No"]).strip()
        pts = []
        for pair in str(raw_r["Plot Area Lat Long"]).strip().split("#"):
            parts = pair.strip().split(",")
            if len(parts) >= 2:
                pts.append((float(parts[1].strip()), float(parts[0].strip())))
        if len(pts) >= 3:
            poly_dict[p_no] = Polygon(pts)

    # 1. Discover Multi-Season Sentinel-2 Scenes from AWS Earth Search STAC (Sorted by Lowest Cloud Cover)
    STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"
    seasonal_windows = [
        ("2025-08-01", "2025-08-30", "Kharif_2025", "2025-08-15"),
        ("2025-11-15", "2025-11-30", "PostMonsoon_2025", "2025-11-20"),
        ("2026-01-20", "2026-01-26", "January_2026", "2026-01-23"),
        ("2026-05-15", "2026-05-30", "Summer_2026", "2026-05-20"),
        ("2026-08-01", "2026-08-16", "Current_August_2026", "2026-08-16")
    ]

    target_tiles = ["43QDB", "43QEB", "43QFB"]
    scenes_by_season_tile = {}

    print("\nDiscovering STAC candidate scenes per tile and season...")
    for start_d, end_d, season_tag, ref_date in seasonal_windows:
        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": [74.85, 19.15, 76.25, 19.70],
            "datetime": f"{start_d}T00:00:00Z/{end_d}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": 15}},
            "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
            "limit": 30
        }
        try:
            resp = requests.post(STAC_ENDPOINT, json=payload, timeout=20).json()
            feats = resp.get("features", [])
            for f in feats:
                tile = f["id"].split("_")[1]
                if tile in target_tiles:
                    key = (season_tag, tile)
                    if key not in scenes_by_season_tile:
                        scenes_by_season_tile[key] = (f, ref_date)
        except Exception as e:
            print(f"  Warning querying {season_tag}: {e}")

    # Group parcels by target tile
    tile_polys = {"43QDB": [], "43QEB": [], "43QFB": []}
    parcel_tile_map = {}

    for idx, r in df_spatial.iterrows():
        pno = str(r["plot_no"]).strip()
        poly_wgs = poly_dict.get(pno)
        if poly_wgs is None:
            continue
        poly_utm = transform(wgs84_to_utm43n, poly_wgs)
        
        c_lon = poly_wgs.centroid.x
        if c_lon < 75.0:
            t = "43QDB"
        elif c_lon > 75.8:
            t = "43QFB"
        else:
            t = "43QEB"

        tile_polys[t].append(poly_utm)
        parcel_tile_map[pno] = t

    tile_envelopes = {}
    for t, plist in tile_polys.items():
        if plist:
            u_poly = unary_union(plist)
            minx, miny, maxx, maxy = u_poly.bounds
            tile_envelopes[t] = (minx - 300.0, miny - 300.0, maxx + 300.0, maxy + 300.0)

    print("\nPreloading Cleanest Tile Sub-Regions into Local Memory...")
    memory_caches = {}

    def load_tile_cache(item):
        (season_tag, tile), (feat, ref_date) = item
        env = tile_envelopes.get(tile)
        if not env:
            return (season_tag, tile), None
        try:
            cache = TileSceneMemoryCache(feat, env)
            return (season_tag, tile), cache
        except Exception as e:
            print(f"  Warning loading {season_tag}-{tile}: {e}")
            return (season_tag, tile), None

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(load_tile_cache, it) for it in scenes_by_season_tile.items()]
        for fut in as_completed(futures):
            k, cache = fut.result()
            if cache and cache.is_valid:
                memory_caches[k] = cache
                print(f"  Cached [{k[0]:<18} | Tile {k[1]}] -> Date: {cache.date}, Cloud: {cache.cloud_pct:.1f}%")

    print(f"\nStreaming fast in-memory extractions across 320 parcels...")
    results = []
    season_order = ["Kharif_2025", "PostMonsoon_2025", "January_2026", "Summer_2026", "Current_August_2026"]

    for idx, r in df_spatial.iterrows():
        pno = str(r["plot_no"]).strip()
        poly_wgs = poly_dict.get(pno)
        target_tile = parcel_tile_map.get(pno, "43QEB")
        if poly_wgs is None:
            continue

        dates_list = []
        ndvi_series = []
        canopy_frac_series = []
        usability_series = []
        date_obs_map = {}

        for st in season_order:
            cache = memory_caches.get((st, target_tile))
            if cache and cache.is_valid:
                obs = cache.extract_parcel(poly_wgs)
                if obs.get("date"):
                    dates_list.append(obs["date"])
                    ndvi_series.append(obs["ndvi"])
                    canopy_frac_series.append(obs["canopy_fraction_pct"])
                    usability_series.append(obs["usability_pct"])
                    date_obs_map[st] = obs

        # Current State Evaluation
        aug_obs = date_obs_map.get("Current_August_2026", {})
        may_obs = date_obs_map.get("Summer_2026", {})
        jan_obs = date_obs_map.get("January_2026", {})
        nov_obs = date_obs_map.get("PostMonsoon_2025", {})

        is_aug_valid = (aug_obs.get("ndvi") is not None) and (aug_obs.get("usability_pct", 0.0) >= 50.0)
        aug_ndvi = aug_obs.get("ndvi") if is_aug_valid else None
        aug_canopy = aug_obs.get("canopy_fraction_pct", 0.0) if is_aug_valid else 0.0
        aug_date = aug_obs.get("date")

        jan_ndvi = jan_obs.get("ndvi") or (float(r["inside_mean_ndvi"]) if pd.notna(r["inside_mean_ndvi"]) else None)
        jan_occ = float(r["inside_canopy_occupancy_pct"]) if pd.notna(r["inside_canopy_occupancy_pct"]) else 0.0
        may_ndvi = may_obs.get("ndvi")

        # Measured 60-90d delta
        delta_60_90d = None
        if aug_ndvi is not None and may_ndvi is not None:
            delta_60_90d = round(aug_ndvi - may_ndvi, 3)

        current_obs_dict = {
            "ndvi": aug_ndvi,
            "canopy_fraction_pct": aug_canopy,
            "date": aug_date,
            "is_valid": is_aug_valid,
            "usability_pct": aug_obs.get("usability_pct", 0.0)
        }

        recent_delta_dict = {
            "delta_ndvi_60_90d": delta_60_90d,
            "days_span": 84
        }

        pheno = extract_phenological_trajectory_features(
            dates=dates_list,
            ndvi_series=ndvi_series,
            scl_usability_series=usability_series
        )

        spatial_ctx = {
            "spatial_discrepancy_stratum": r.get("spatial_discrepancy_stratum"),
            "nearest_high_canopy_dist_m": r.get("nearest_high_canopy_dist_m"),
            "ring_25m_canopy_pct": r.get("ring_25m_canopy_pct"),
            "ring_50m_canopy_pct": r.get("ring_50m_canopy_pct")
        }

        diag = evaluate_spatio_temporal_profile(
            current_obs=current_obs_dict,
            pheno_features=pheno,
            spatial_context=spatial_ctx,
            recent_delta_obs=recent_delta_dict,
            dates_list=dates_list,
            ndvi_series=ndvi_series,
            canopy_frac_series=canopy_frac_series,
            january_canopy_occ=jan_occ
        )

        results.append({
            "plot_no": pno,
            "farmer_name": r["farmer_name"],
            "village": r["village"],
            "geometry_group_id": r.get("geometry_group_id"),
            "is_duplicate_geometry": r.get("is_duplicate_geometry"),
            "measured_aug25_ndvi": date_obs_map.get("Kharif_2025", {}).get("ndvi"),
            "measured_nov25_ndvi": date_obs_map.get("PostMonsoon_2025", {}).get("ndvi"),
            "measured_jan26_ndvi": jan_ndvi,
            "measured_may26_ndvi": may_ndvi,
            "measured_aug26_ndvi": aug_ndvi,
            "measured_nov25_direct_canopy_pct": date_obs_map.get("PostMonsoon_2025", {}).get("canopy_fraction_pct"),
            "measured_jan26_direct_canopy_pct": jan_obs.get("canopy_fraction_pct"),
            "measured_aug26_direct_canopy_pct": aug_canopy,
            "measured_60_90d_delta_ndvi": delta_60_90d,
            "measured_green_duration_days": pheno["green_duration_days"],
            "measured_max_annual_ndvi": pheno["max_ndvi"],
            "canopy_collapse_detected": diag.get("collapse_event", {}).get("collapse_detected", False),
            "canopy_collapse_window": diag.get("collapse_event", {}).get("clearing_window"),
            "canopy_collapse_drop_magnitude_ndvi": diag.get("collapse_event", {}).get("drop_magnitude_ndvi", 0.0),
            "canopy_collapse_drop_magnitude_canopy_pp": diag.get("collapse_event", {}).get("drop_magnitude_canopy_pp", 0.0),
            "canopy_collapse_gap_days": diag.get("collapse_event", {}).get("gap_days", 0),
            "current_vegetative_state": diag["current_vegetative_state"],
            "spatial_neighborhood_flag": diag["spatial_neighborhood_flag"],
            "phenological_profile_type": diag["phenological_profile_type"],
            "spatio_temporal_status": diag["spatio_temporal_status"],
            "operational_mill_action": diag["operational_mill_action"],
            "current_observation_valid": diag.get("current_observation_valid", False),
            "current_observation_age_days": diag.get("current_observation_age_days"),
            "nearest_high_canopy_dist_m": r.get("nearest_high_canopy_dist_m"),
            "diagnostic_rationale": diag["diagnostic_rationale"]
        })

    df_out = pd.DataFrame(results)
    out_path = os.path.join(REPO_ROOT, output_csv)
    df_out.to_csv(out_path, index=False)
    print(f"\nSaved master dataset to: {out_path}")

    # Extract 54 low-canopy parcel subset
    low54_pnos = set(df_spatial[df_spatial["diagnostic_stratum"] == "NO_STANDING_VEGETATION_OR_FALLOW"]["plot_no"].astype(str))
    df_54 = df_out[df_out["plot_no"].astype(str).isin(low54_pnos)]
    out_54_path = os.path.join(REPO_ROOT, output_54_csv)
    df_54.to_csv(out_54_path, index=False)
    print(f"Saved 54 low-canopy audit dataset to: {out_54_path}")

    elapsed = round(time.time() - start_time, 2)
    print(f"\n⚡ Total Execution Time: {elapsed} seconds (across 320 parcels x 5 seasons)")

    print("\n==================================================================")
    print(" EMPIRICAL SPATIO-TEMPORAL AUDIT SUMMARY (320 REGISTERED PARCELS)")
    print("==================================================================")
    for status, grp in df_out.groupby("spatio_temporal_status"):
        unique_units = grp["geometry_group_id"].nunique()
        print(f"  • {status:<55}: {len(grp):>3} records ({len(grp)/len(df_out)*100.0:>5.1f}%) | {unique_units:>3} unique land units")

    print("\n==================================================================")
    print(" RESOLUTION OF THE 54 LOW-CANOPY PARCELS FROM REAL SENTINEL PIXELS")
    print("==================================================================")
    print(f"Total Low-Canopy Records: {len(df_54)} | Unique Land Units: {df_54['geometry_group_id'].nunique()}")
    for status, grp in df_54.groupby("spatio_temporal_status"):
        unique_units = grp["geometry_group_id"].nunique()
        print(f"  • {status:<55}: {len(grp):>2} / {len(df_54)} records ({len(grp)/len(df_54)*100.0:>5.1f}%) | {unique_units} unique units")

if __name__ == "__main__":
    run_empirical_spatio_temporal_audit()