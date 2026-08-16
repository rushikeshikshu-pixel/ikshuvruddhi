"""
ml/phenology_features.py
Multi-Temporal Phenological Feature Extraction for Crop Type Discrimination
Extracts temporal trajectory parameters (Green Season Duration, AUC, Senescence Rate, Moisture Retention)
from multi-date Sentinel-2 observations (NDVI, NDRE, LSWI).
"""

import math
import numpy as np
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

def extract_phenological_trajectory_features(
    dates: List[str],               # ISO date strings: ['2025-07-01', '2025-08-15', ...]
    ndvi_series: List[float],       # Polygon-masked mean NDVI values
    ndre_series: Optional[List[float]] = None, # Mean NDRE (B08-B05)/(B08+B05)
    lswi_series: Optional[List[float]] = None, # Mean LSWI (B08-B11)/(B08+B11)
    scl_usability_series: Optional[List[float]] = None, # Usable pixel fraction (0-100%)
    min_ndvi_green_threshold: float = 0.45,
    min_usability_pct: float = 85.0
) -> Dict[str, Any]:
    """
    Extracts phenological features from time-series observations.
    Filters invalid/cloudy dates and computes:
      - green_duration_days: Number of days maintaining NDVI >= threshold
      - ndvi_auc: Numerical integral of NDVI over total observation span (AUC)
      - max_ndvi, min_ndvi, mean_ndvi: Basic distribution statistics
      - senescence_rate_per_day: Maximum drop in NDVI per day during dry-down / harvest
      - mean_ripening_lswi: Mean LSWI in the second half of the observation window
      - mean_ripening_ndre: Mean NDRE in the second half of the observation window
    """
    if len(dates) == 0 or len(ndvi_series) == 0 or len(dates) != len(ndvi_series):
        return {
            "valid_observations_count": 0,
            "observation_span_days": 0,
            "green_duration_days": 0,
            "ndvi_auc": 0.0,
            "max_ndvi": 0.0,
            "min_ndvi": 0.0,
            "mean_ndvi": 0.0,
            "senescence_rate_per_day": 0.0,
            "mean_ripening_lswi": 0.0,
            "mean_ripening_ndre": 0.0,
            "is_perennial_profile": False
        }

    # Filter by usability & sort by date
    parsed_points = []
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

        ndre_val = ndre_series[idx] if (ndre_series and idx < len(ndre_series) and ndre_series[idx] is not None and not np.isnan(ndre_series[idx])) else 0.0
        lswi_val = lswi_series[idx] if (lswi_series and idx < len(lswi_series) and lswi_series[idx] is not None and not np.isnan(lswi_series[idx])) else 0.0

        parsed_points.append((dt, ndvi_val, ndre_val, lswi_val))

    parsed_points.sort(key=lambda x: x[0])
    valid_count = len(parsed_points)
    if valid_count < 2:
        return {
            "valid_observations_count": valid_count,
            "observation_span_days": 0,
            "green_duration_days": 0,
            "ndvi_auc": 0.0,
            "max_ndvi": parsed_points[0][1] if valid_count == 1 else 0.0,
            "min_ndvi": parsed_points[0][1] if valid_count == 1 else 0.0,
            "mean_ndvi": parsed_points[0][1] if valid_count == 1 else 0.0,
            "senescence_rate_per_day": 0.0,
            "mean_ripening_lswi": parsed_points[0][3] if valid_count == 1 else 0.0,
            "mean_ripening_ndre": parsed_points[0][2] if valid_count == 1 else 0.0,
            "is_perennial_profile": False
        }

    start_dt = parsed_points[0][0]
    end_dt = parsed_points[-1][0]
    total_span_days = max(1, (end_dt - start_dt).days)

    # Compute numerical trapezoidal integral (AUC) & green duration
    total_auc = 0.0
    green_duration_days = 0
    max_senescence_rate = 0.0
    all_ndvis = [p[1] for p in parsed_points]

    midpoint_dt = start_dt + (end_dt - start_dt) / 2
    ripening_lswis = []
    ripening_ndres = []

    for i in range(len(parsed_points) - 1):
        dt_i, ndvi_i, ndre_i, lswi_i = parsed_points[i]
        dt_next, ndvi_next, ndre_next, lswi_next = parsed_points[i + 1]
        
        delta_days = max(1, (dt_next - dt_i).days)
        # Trapezoidal area = avg(ndvi) * days
        trap_area = ((ndvi_i + ndvi_next) / 2.0) * delta_days
        total_auc += trap_area

        if ndvi_i >= min_ndvi_green_threshold and ndvi_next >= min_ndvi_green_threshold:
            green_duration_days += delta_days
        elif ndvi_i >= min_ndvi_green_threshold or ndvi_next >= min_ndvi_green_threshold:
            # Interpolate fraction of time above threshold
            if ndvi_next != ndvi_i:
                frac = abs((min_ndvi_green_threshold - ndvi_i) / (ndvi_next - ndvi_i))
                frac = min(1.0, max(0.0, frac))
                green_duration_days += int(round(delta_days * (1.0 - frac)))

        # Track steep drop (senescence / harvest)
        if delta_days > 0 and ndvi_next < ndvi_i:
            drop_rate = (ndvi_i - ndvi_next) / delta_days
            if drop_rate > max_senescence_rate:
                max_senescence_rate = drop_rate

        if dt_i >= midpoint_dt:
            ripening_lswis.append(lswi_i)
            ripening_ndres.append(ndre_i)

    # Add last point to ripening list if applicable
    if parsed_points[-1][0] >= midpoint_dt:
        ripening_lswis.append(parsed_points[-1][3])
        ripening_ndres.append(parsed_points[-1][2])

    mean_ripening_lswi = float(np.mean(ripening_lswis)) if ripening_lswis else float(np.mean([p[3] for p in parsed_points]))
    mean_ripening_ndre = float(np.mean(ripening_ndres)) if ripening_ndres else float(np.mean([p[2] for p in parsed_points]))

    is_perennial = (green_duration_days >= 200) and (total_span_days >= 240)

    return {
        "valid_observations_count": valid_count,
        "observation_span_days": total_span_days,
        "green_duration_days": int(green_duration_days),
        "ndvi_auc": round(total_auc, 1),
        "normalized_annual_auc": round((total_auc / total_span_days) * 365.0, 1),
        "max_ndvi": round(float(np.max(all_ndvis)), 3),
        "min_ndvi": round(float(np.min(all_ndvis)), 3),
        "mean_ndvi": round(float(np.mean(all_ndvis)), 3),
        "senescence_rate_per_day": round(max_senescence_rate, 4),
        "mean_ripening_lswi": round(mean_ripening_lswi, 3),
        "mean_ripening_ndre": round(mean_ripening_ndre, 3),
        "is_perennial_profile": is_perennial
    }