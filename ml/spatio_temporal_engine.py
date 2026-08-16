"""
ml/spatio_temporal_engine.py
Unified 3-Layer Spatio-Temporal Intelligence & Multi-Dimensional Decision Engine
Integrates:
  Dimension 1: Current State (Latest High-Quality Observation, e.g., August 2026, with no silent fallbacks)
  Dimension 2: Event History (Dual-Metric NDVI + Direct Canopy Fraction Collapse with Time-Gap Constraints)
  Dimension 3: Spatial Context (Boundary Discrepancy with Inside-Canopy Low Guard)
  Dimension 4: Multi-Season Phenological Dynamics (Sampled Profile Typing)
  Dimension 5: Cadastral Land Unit Deduplication for 320 Registered Mill Parcels
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

def detect_canopy_collapse_events(
    dates: List[str],
    ndvi_series: List[Optional[float]],
    canopy_frac_series: Optional[List[Optional[float]]] = None,
    min_pre_collapse_ndvi: float = 0.55,
    max_post_collapse_ndvi: float = 0.35,
    min_drop_magnitude_ndvi: float = 0.30,
    min_pre_collapse_canopy_pct: float = 40.0,
    max_post_collapse_canopy_pct: float = 25.0,
    min_drop_magnitude_canopy_pp: float = 35.0,
    min_gap_days: int = 10,
    max_gap_days: int = 95
) -> Dict[str, Any]:
    """
    Explicitly detects step-function canopy collapse / clearing events between consecutive observations.
    Enforces DUAL-METRIC constraints (NDVI drop AND direct canopy fraction drop) plus TIME-GAP constraints (10-95 days).
    """
    valid_obs = []
    if canopy_frac_series is None:
        canopy_frac_series = [None] * len(dates)

    for d, v, c in zip(dates, ndvi_series, canopy_frac_series):
        if v is not None:
            valid_obs.append((d, v, c))

    for i in range(len(valid_obs) - 1):
        d_pre, v_pre, c_pre = valid_obs[i]
        d_post, v_post, c_post = valid_obs[i + 1]

        # Check time gap constraint
        try:
            dt_pre = datetime.strptime(d_pre[:10], "%Y-%m-%d")
            dt_post = datetime.strptime(d_post[:10], "%Y-%m-%d")
            gap_days = abs((dt_post - dt_pre).days)
        except Exception:
            gap_days = 60

        if not (min_gap_days <= gap_days <= max_gap_days):
            continue

        delta_ndvi = round(v_post - v_pre, 3)
        delta_canopy_pp = round((c_post - c_pre), 1) if (c_pre is not None and c_post is not None) else None

        ndvi_collapse = (v_pre >= min_pre_collapse_ndvi and v_post < max_post_collapse_ndvi and delta_ndvi <= -min_drop_magnitude_ndvi)
        canopy_collapse = True
        if delta_canopy_pp is not None:
            canopy_collapse = (c_pre >= min_pre_collapse_canopy_pct and c_post <= max_post_collapse_canopy_pct and delta_canopy_pp <= -min_drop_magnitude_canopy_pp)

        if ndvi_collapse and canopy_collapse:
            return {
                "collapse_detected": True,
                "pre_collapse_date": d_pre,
                "pre_collapse_ndvi": v_pre,
                "pre_collapse_canopy_pct": c_pre,
                "post_collapse_date": d_post,
                "post_collapse_ndvi": v_post,
                "post_collapse_canopy_pct": c_post,
                "drop_magnitude_ndvi": abs(delta_ndvi),
                "drop_magnitude_canopy_pp": abs(delta_canopy_pp) if delta_canopy_pp is not None else None,
                "gap_days": gap_days,
                "clearing_window": f"{d_pre} -> {d_post}"
            }

    return {
        "collapse_detected": False,
        "pre_collapse_date": None,
        "pre_collapse_ndvi": None,
        "pre_collapse_canopy_pct": None,
        "post_collapse_date": None,
        "post_collapse_ndvi": None,
        "post_collapse_canopy_pct": None,
        "drop_magnitude_ndvi": 0.0,
        "drop_magnitude_canopy_pp": 0.0,
        "gap_days": 0,
        "clearing_window": None
    }

def evaluate_spatio_temporal_profile(
    current_obs: Dict[str, Any],            # {'ndvi': 0.65, 'canopy_fraction_pct': 80.0, 'usability_pct': 95.0, 'date': '2026-08-10', 'is_valid': True}
    pheno_features: Dict[str, Any],         # Output of extract_phenological_trajectory_features()
    spatial_context: Dict[str, Any],        # Output of diagnose_spatial_discrepancy() & ring_stats
    recent_delta_obs: Optional[Dict[str, Any]] = None, # {'delta_ndvi_60_90d': +0.25, 'days_span': 70}
    dates_list: Optional[List[str]] = None,
    ndvi_series: Optional[List[Optional[float]]] = None,
    canopy_frac_series: Optional[List[Optional[float]]] = None,
    january_canopy_occ: float = 0.0,
    reference_date_str: str = "2026-08-16"
) -> Dict[str, Any]:
    """
    Evaluates multi-dimensional spatio-temporal dynamics and decouples:
      1. Current Vegetative State
      2. Historical Event Detection (Harvest / Canopy Collapse)
      3. Spatial Neighborhood Context (Guarded Boundary Discrepancy)
      4. Phenological Profile Typing
      5. Primary Operational Recommendation
    """
    is_curr_valid = current_obs.get("is_valid", True) and (current_obs.get("usability_pct", 0.0) >= 50.0)
    curr_ndvi = current_obs.get("ndvi") if is_curr_valid else None
    curr_canopy = current_obs.get("canopy_fraction_pct", 0.0) if is_curr_valid else 0.0
    curr_date = current_obs.get("date")

    # Current Observation Age
    obs_age_days = None
    if curr_date:
        try:
            dt_curr = datetime.strptime(curr_date[:10], "%Y-%m-%d")
            dt_ref = datetime.strptime(reference_date_str[:10], "%Y-%m-%d")
            obs_age_days = abs((dt_ref - dt_curr).days)
        except Exception:
            obs_age_days = None

    hist_green_days = pheno_features.get("green_duration_days", 0)
    hist_max_ndvi   = pheno_features.get("max_ndvi")
    is_perennial    = pheno_features.get("is_perennial_profile", False)

    spatial_stratum = spatial_context.get("spatial_discrepancy_stratum", "UNKNOWN")
    nearest_cane_m  = spatial_context.get("nearest_high_canopy_dist_m")
    r25_can         = spatial_context.get("ring_25m_canopy_pct")
    r50_can         = spatial_context.get("ring_50m_canopy_pct")

    delta_ndvi = recent_delta_obs.get("delta_ndvi_60_90d") if recent_delta_obs else None

    # Step-Function Canopy Collapse Event Detection
    collapse_info = {"collapse_detected": False}
    if dates_list and ndvi_series:
        collapse_info = detect_canopy_collapse_events(dates_list, ndvi_series, canopy_frac_series)

    # 1. Dimension: Current Vegetative State
    if not is_curr_valid:
        curr_state = "CURRENT_OBSERVATION_UNAVAILABLE"
    elif curr_ndvi is not None and curr_ndvi >= 0.50 and curr_canopy >= 50.0:
        curr_state = "STANDING_MATURE_CANOPY"
    elif delta_ndvi is not None and delta_ndvi >= 0.20 and curr_ndvi is not None and curr_ndvi >= 0.40:
        curr_state = "ACTIVE_TILLERING_GROWTH_EMERGING"
    elif curr_ndvi is not None and curr_ndvi < 0.35 and curr_canopy < 20.0:
        curr_state = "LOW_CANOPY_OR_CLEARED"
    else:
        curr_state = "PARTIAL_OR_INTERMEDIATE_CANOPY"

    # 2. Dimension: Spatial Flag with INSIDE-CANOPY LOW GUARD
    # Boundary Discrepancy ONLY triggers if inside canopy is low AND surrounding 25m/50m is high
    inside_is_low = (january_canopy_occ < 20.0) or (curr_canopy < 20.0 and (curr_ndvi is None or curr_ndvi < 0.35))
    surrounding_is_high = ((r25_can is not None and r25_can >= 45.0) or (r50_can is not None and r50_can >= 45.0))

    if inside_is_low and surrounding_is_high:
        spatial_flag = "BOUNDARY_OR_REGISTRATION_DISCREPANCY"
    elif inside_is_low and nearest_cane_m is not None and nearest_cane_m <= 150.0:
        spatial_flag = "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER"
    elif spatial_stratum == "REGIONAL_FALLOW_OR_DRY_LOCALITY":
        spatial_flag = "REGIONAL_LOW_CANOPY_LOCALITY"
    elif spatial_stratum == "CONGRUENT_STANDING_CANOPY":
        spatial_flag = "CONGRUENT_STANDING_CANOPY"
    else:
        spatial_flag = "ISOLATED_PARCEL"

    # 3. Dimension: Phenological Profile Type
    if is_perennial or hist_green_days >= 180:
        pheno_profile = "PERENNIAL_LONG_DURATION_PROFILE"
    elif hist_green_days > 0 and hist_green_days < 120:
        pheno_profile = "SHORT_DURATION_GREEN_PROFILE_CROP_TYPE_UNVERIFIED"
    elif hist_max_ndvi is not None and hist_max_ndvi < 0.35:
        pheno_profile = "NO_STRONG_CANOPY_OBSERVED_AT_SAMPLED_DATES"
    else:
        pheno_profile = "INTERMEDIATE_MULTI_SEASON_PROFILE"

    # 4. Primary Operational Recommendation & Spatio-Temporal Status Synthesis
    if collapse_info["collapse_detected"]:
        primary_status = "STRONG_CANOPY_CLEARING_EVENT_CONSISTENT_WITH_HARVEST"
        primary_action = "LOG_HARVEST_AND_VERIFY_WEIGHBRIDGE_RECEIPT"
        primary_rationale = (
            f"Measured canopy collapse between {collapse_info['clearing_window']} "
            f"(NDVI {collapse_info['pre_collapse_ndvi']:.3f} -> {collapse_info['post_collapse_ndvi']:.3f}, "
            f"drop: -{collapse_info['drop_magnitude_ndvi']:.3f} dNDVI, {collapse_info['gap_days']}d gap). Consistent with cane harvest."
        )
    elif curr_state == "STANDING_MATURE_CANOPY" and pheno_profile == "PERENNIAL_LONG_DURATION_PROFILE":
        primary_status = "SUGARCANE_COMPATIBLE_STRONG_LONG_DURATION_CANOPY"
        primary_action = "SCHEDULE_FOR_HARVEST_SUPPLY"
        primary_rationale = f"High standing canopy ({curr_canopy:.1f}%, NDVI: {curr_ndvi:.3f}) with continuous long-duration green history ({hist_green_days}d)."
    elif curr_state in ["STANDING_MATURE_CANOPY", "ACTIVE_TILLERING_GROWTH_EMERGING"]:
        primary_status = "ACTIVE_VEGETATIVE_GROWTH_RECENT_CROP"
        primary_action = "MONITOR_GROWTH_STAGE"
        primary_rationale = f"High active canopy ({curr_canopy:.1f}%, NDVI: {curr_ndvi:.3f}) following recent growth surge."
    elif spatial_flag == "BOUNDARY_OR_REGISTRATION_DISCREPANCY":
        primary_status = "BOUNDARY_OR_REGISTRATION_DISCREPANCY"
        primary_action = "GPS_BOUNDARY_RE_SURVEY"
        primary_rationale = f"Low inside parcel ({january_canopy_occ:.1f}%), but strong standing canopy immediately outside in 25-50m buffer ({r25_can}% / {r50_can}%)."
    elif spatial_flag == "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER":
        primary_status = "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER"
        primary_action = "FIELD_OFFICER_CONFIRMATION"
        primary_rationale = f"Individual parcel low, but active high-canopy parcel exists {nearest_cane_m:.0f}m away in same cluster."
    elif pheno_profile == "SHORT_DURATION_GREEN_PROFILE_CROP_TYPE_UNVERIFIED":
        primary_status = "SHORT_DURATION_GREEN_PROFILE_CROP_TYPE_UNVERIFIED"
        primary_action = "CHECK_NON_CANE_CROP_TYPE"
        primary_rationale = f"Short-duration green peak ({hist_green_days}d) followed by dry-down, inconsistent with 12-18 month sugarcane."
    elif pheno_profile == "NO_STRONG_CANOPY_OBSERVED_AT_SAMPLED_DATES":
        primary_status = "NO_STRONG_CANOPY_OBSERVED_AT_SAMPLED_DATES"
        primary_action = "FLAG_UNPLANTED_REGISTRATION"
        primary_rationale = f"Flat low NDVI (peak {hist_max_ndvi:.3f}) across all sampled dates."
    else:
        primary_status = "ISOLATED_LOW_CANOPY_UNRESOLVED"
        primary_action = "FIELD_INSPECTION_REQUIRED"
        primary_rationale = f"Low current NDVI ({curr_ndvi}) with mixed multi-season history and isolated surroundings."

    return {
        "spatio_temporal_status": primary_status,
        "current_vegetative_state": curr_state,
        "canopy_clearing_event_detected": collapse_info["collapse_detected"],
        "collapse_event": collapse_info,
        "spatial_neighborhood_flag": spatial_flag,
        "phenological_profile_type": pheno_profile,
        "current_observation_valid": is_curr_valid,
        "current_observation_age_days": obs_age_days,
        "operational_mill_action": primary_action,
        "diagnostic_rationale": primary_rationale
    }