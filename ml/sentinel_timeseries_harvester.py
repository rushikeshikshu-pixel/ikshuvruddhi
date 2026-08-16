"""
ml/sentinel_timeseries_harvester.py
Multi-Temporal Sentinel-2 L2A Time-Series Harvester & Quality-Ranked Scene Selector
Fetches and ranks multi-date Sentinel-2 observations across 12-18 month historical windows and recent August 2026 data.
"""

import os
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
import numpy as np

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"

def rank_scene_quality(
    parcel_valid_coverage_pct: float,
    cloud_cover_pct: float,
    acquisition_datetime: str,
    target_reference_datetime: Optional[str] = None,
    usability_weight: float = 0.60,
    cloud_weight: float = 0.20,
    recency_weight: float = 0.20
) -> float:
    """
    Ranks observation quality using multi-criteria weighted scoring:
      - Parcel Valid Usability (0-100)
      - Scene Cloud Cleanliness (100 - cloud_cover)
      - Temporal Recency / Proximity to Target Date
    """
    # Usability score (0 - 100)
    usability_score = min(100.0, max(0.0, parcel_valid_coverage_pct))

    # Cloud score (0 - 100)
    cloud_score = max(0.0, 100.0 - (cloud_cover_pct * 2.0))

    # Recency score (0 - 100)
    if target_reference_datetime:
        target_dt = datetime.strptime(target_reference_datetime[:10], "%Y-%m-%d")
    else:
        target_dt = datetime.utcnow()
        
    try:
        scene_dt = datetime.strptime(acquisition_datetime[:10], "%Y-%m-%d")
        days_diff = abs((target_dt - scene_dt).days)
        # Score decreases smoothly over 60 days
        recency_score = max(0.0, 100.0 - (days_diff * 1.5))
    except Exception:
        recency_score = 50.0

    total_score = (
        usability_score * usability_weight +
        cloud_score * cloud_weight +
        recency_score * recency_weight
    )
    return round(total_score, 2)

def query_tile_multidate_catalog(
    bbox: List[float] = [74.85, 19.15, 76.25, 19.70],
    start_date: str = "2025-06-01",
    end_date: str = "2026-08-16",
    max_cloud_cover: float = 25.0
) -> List[Dict[str, Any]]:
    """
    Queries Earth Search STAC for all available Sentinel-2 scenes across the multi-season window.
    """
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{start_date}T00:00:00Z/{end_date}T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": max_cloud_cover}},
        "limit": 100
    }
    try:
        resp = requests.post(STAC_ENDPOINT, json=payload, timeout=20).json()
        return resp.get("features", [])
    except Exception as e:
        print(f"Warning: STAC query failed ({e}), returning empty list.")
        return []