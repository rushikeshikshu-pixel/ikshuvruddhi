"""
ml/phenology_features.py
Multi-Temporal Phenological Feature Extraction for Crop Type Discrimination
Extracts temporal trajectory parameters (Green Season Duration, AUC, Senescence Rate, Moisture Retention)
from multi-date Sentinel-2 observations (NDVI, NDRE, LSWI).

Scientifically Hardened Rules:
  1. Exact Directional Interpolation: Corrects upward vs. downward threshold crossing math for green duration.
  2. Late-Window Terminology: Renamed from 'ripening' to 'late_window' to reflect observational half rather than unconfirmed agronomic stage.
  3. Temporal Distribution Tracking: Computes `temporal_monthly_coverage_pct` to verify observation distribution across distinct months.
  4. Missing Data Integrity: Preserves None/NaN for missing spectral bands without manufacturing artificial zeros.
"""

import math
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

def extract_phenological_trajectory_features(
    dates: List[str],               # ISO date strings: ['2025-07-01', '2025-08-15', ...]
    ndvi_series: List[float],       # Polygon-masked mean NDVI values
    ndre_series: Optional[List[Optional[float]]] = None, # Mean NDRE (B08-B05)/(B08+B05)
    lswi_series: Optional[List[Optional[float]]] = None, # Mean LSWI (B08-B11)/(B08+B11)
    scl_usability_series: Optional[List[float]] = None, # Usable pixel fraction (0-100%)
    min_ndvi_green_threshold: float = 0.45,
    min_usability_pct: float = 85.0
) -> Dict[str, Any]:
    """
    Extracts phenological features from time-series observations.
    Computes exact trapezoidal integral and directional duration interpolation.
    """
    if len(dates) == 0 or len(ndvi_series) == 0 or len(dates) != len(ndvi_series):
        return {
            "valid_observations_count": 0,
            "observation_span_days": 0,
            "temporal_monthly_coverage_pct": 0.0,
            "green_duration_days": 0,
            "ndvi_auc": 0.0,
            "max_ndvi": None,
            "min_ndvi": None,
            "mean_ndvi": None,
            "senescence_rate_per_day": 0.0,
            "late_window_mean_lswi": None,
            "late_window_mean_ndre": None,
            "is_perennial_profile": False
        }

    parsed_points = []
    unique_months = set()

    for idx, d_str in enumerate(dates):
        try:
            dt = datetime.strptime(d_str[:10], "%Y-%m-%d")
        except Exception:
            continue
            
        ndvi_val = ndvi_series[idx]
        if ndvi_val is None or np.isnan(ndvi_val):
            continue

        usability = scl_usability_series[idx] if (scl_usability_series and idx < len(scl_usability_series)) else 100.0
        if usability < min_usability_pct:
            continue

        ndre_val = None
        if ndre_series and idx < len(ndre_series):
            raw_ndre = ndre_series[idx]
            if raw_ndre is not None and not np.isnan(raw_ndre):
                ndre_val = float(raw_ndre)

        lswi_val = None
        if lswi_series and idx < len(lswi_series):
            raw_lswi = lswi_series[idx]
            if raw_lswi is not None and not np.isnan(raw_lswi):
                lswi_val = float(raw_lswi)

        parsed_points.append((dt, float(ndvi_val), ndre_val, lswi_val))
        unique_months.add((dt.year, dt.month))

    parsed_points.sort(key=lambda x: x[0])
    valid_count = len(parsed_points)
    if valid_count < 2:
        return {
            "valid_observations_count": valid_count,
            "observation_span_days": 0,
            "temporal_monthly_coverage_pct": 0.0,
            "green_duration_days": 0,
            "ndvi_auc": 0.0,
            "max_ndvi": parsed_points[0][1] if valid_count == 1 else None,
            "min_ndvi": parsed_points[0][1] if valid_count == 1 else None,
            "mean_ndvi": parsed_points[0][1] if valid_count == 1 else None,
            "senescence_rate_per_day": 0.0,
            "late_window_mean_lswi": parsed_points[0][3] if valid_count == 1 else None,
            "late_window_mean_ndre": parsed_points[0][2] if valid_count == 1 else None,
            "is_perennial_profile": False
        }

    start_dt = parsed_points[0][0]
    end_dt = parsed_points[-1][0]
    total_span_days = max(1, (end_dt - start_dt).days)
    total_span_months = max(1.0, total_span_days / 30.4375)
    monthly_cov_pct = min(100.0, (len(unique_months) / total_span_months) * 100.0)

    total_auc = 0.0
    green_duration_days = 0.0
    max_senescence_rate = 0.0
    all_ndvis = [p[1] for p in parsed_points]

    midpoint_dt = start_dt + (end_dt - start_dt) / 2
    late_lswis = []
    late_ndres = []

    for i in range(len(parsed_points) - 1):
        dt_i, ndvi_i, ndre_i, lswi_i = parsed_points[i]
        dt_next, ndvi_next, ndre_next, lswi_next = parsed_points[i + 1]
        
        delta_days = max(1, (dt_next - dt_i).days)
        trap_area = ((ndvi_i + ndvi_next) / 2.0) * delta_days
        total_auc += trap_area

        thresh = min_ndvi_green_threshold
        if ndvi_i >= thresh and ndvi_next >= thresh:
            green_duration_days += delta_days
        elif ndvi_i < thresh and ndvi_next >= thresh:
            frac_above = (ndvi_next - thresh) / max(1e-5, (ndvi_next - ndvi_i))
            green_duration_days += delta_days * min(1.0, max(0.0, frac_above))
        elif ndvi_i >= thresh and ndvi_next < thresh:
            frac_above = (ndvi_i - thresh) / max(1e-5, (ndvi_i - ndvi_next))
            green_duration_days += delta_days * min(1.0, max(0.0, frac_above))

        if delta_days > 0 and ndvi_next < ndvi_i:
            drop_rate = (ndvi_i - ndvi_next) / float(delta_days)
            if drop_rate > max_senescence_rate:
                max_senescence_rate = drop_rate

        if dt_i >= midpoint_dt:
            if lswi_i is not None: late_lswis.append(lswi_i)
            if ndre_i is not None: late_ndres.append(ndre_i)

    if parsed_points[-1][0] >= midpoint_dt:
        if parsed_points[-1][3] is not None: late_lswis.append(parsed_points[-1][3])
        if parsed_points[-1][2] is not None: late_ndres.append(parsed_points[-1][2])

    late_window_lswi = float(np.mean(late_lswis)) if late_lswis else None
    late_window_ndre = float(np.mean(late_ndres)) if late_ndres else None

    is_perennial = (green_duration_days >= 200) and (total_span_days >= 240)

    return {
        "valid_observations_count": valid_count,
        "observation_span_days": total_span_days,
        "temporal_monthly_coverage_pct": round(monthly_cov_pct, 1),
        "green_duration_days": int(round(green_duration_days)),
        "ndvi_auc": round(total_auc, 1),
        "normalized_annual_auc": round((total_auc / total_span_days) * 365.0, 1),
        "max_ndvi": round(float(np.max(all_ndvis)), 3),
        "min_ndvi": round(float(np.min(all_ndvis)), 3),
        "mean_ndvi": round(float(np.mean(all_ndvis)), 3),
        "senescence_rate_per_day": round(max_senescence_rate, 4),
        "late_window_mean_lswi": round(late_window_lswi, 3) if late_window_lswi is not None else None,
        "late_window_mean_ndre": round(late_window_ndre, 3) if late_window_ndre is not None else None,
        "is_perennial_profile": is_perennial
    }