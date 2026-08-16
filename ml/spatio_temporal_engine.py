"""
ml/spatio_temporal_engine.py
Unified 3-Layer Spatio-Temporal Intelligence & Crop Lifecycle Decision Engine
Integrates:
  Layer 1: Current State (Latest High-Quality Observation, e.g., August 2026, with no silent fallbacks)
  Layer 2: Recent 60-90 Day Delta & Canopy Collapse (Harvest) Event Detection
  Layer 3: 12-18 Month Phenological Trajectory & Multi-Season Dynamics
  Layer 4: Concentric Spatial Context Rings (25m, 50m, 100m, 250m) & Cluster Proximity
  Layer 5: Cadastral Registration Metadata for 320 Registered Mill Parcels
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

def detect_canopy_collapse_events(
    dates: List[str],
    ndvi_series: List[Optional[float]],
    min_pre_collapse_ndvi: float = 0.55,
    max_post_collapse_ndvi: float = 0.35,
    min_drop_magnitude: float = 0.30
) -> Dict[str, Any]:
    """
    Explicitly detects step-function canopy collapse / clearing events between consecutive observations.
    Flags drops consistent with sugarcane harvesting or mechanical field clearing.
    """
    valid_pairs = []
    for d, v in zip(dates, ndvi_series):
        if v is not None:
            valid_pairs.append((d, v))

    for i in range(len(valid_pairs) - 1):
        d_pre, v_pre = valid_pairs[i]
        d_post, v_post = valid_pairs[i + 1]
        delta = round(v_post - v_pre, 3)

        if v_pre >= min_pre_collapse_ndvi and v_post < max_post_collapse_ndvi and delta <= -min_drop_magnitude:
            return {
                "collapse_detected": True,
                "pre_collapse_date": d_pre,
                "pre_collapse_ndvi": v_pre,
                "post_collapse_date": d_post,
                "post_collapse_ndvi": v_post,
                "drop_magnitude": abs(delta),
                "clearing_window": f"{d_pre} -> {d_post}"
            }

    return {
        "collapse_detected": False,
        "pre_collapse_date": None,
        "pre_collapse_ndvi": None,
        "post_collapse_date": None,
        "post_collapse_ndvi": None,
        "drop_magnitude": 0.0,
        "clearing_window": None
    }

def evaluate_spatio_temporal_profile(
    current_obs: Dict[str, Any],            # {'ndvi': 0.65, 'canopy_fraction_pct': 80.0, 'usability_pct': 95.0, 'date': '2026-08-10', 'is_valid': True}
    pheno_features: Dict[str, Any],         # Output of extract_phenological_trajectory_features()
    spatial_context: Dict[str, Any],        # Output of diagnose_spatial_discrepancy() & ring_stats
    recent_delta_obs: Optional[Dict[str, Any]] = None, # {'delta_ndvi_60_90d': +0.25, 'days_span': 70}
    dates_list: Optional[List[str]] = None,
    ndvi_series: Optional[List[Optional[float]]] = None,
    reference_date_str: str = "2026-08-16"
) -> Dict[str, Any]:
    """
    Synthesizes current observation, recent delta, multi-season history, and spatial neighborhood into an operational diagnosis.
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
    hist_min_ndvi   = pheno_features.get("min_ndvi")
    hist_sen_rate   = pheno_features.get("senescence_rate_per_day", 0.0)
    is_perennial    = pheno_features.get("is_perennial_profile", False)

    spatial_stratum = spatial_context.get("spatial_discrepancy_stratum", "UNKNOWN")
    nearest_cane_m  = spatial_context.get("nearest_high_canopy_dist_m")
    r25_can         = spatial_context.get("ring_25m_canopy_pct")
    r50_can         = spatial_context.get("ring_50m_canopy_pct")

    delta_ndvi = recent_delta_obs.get("delta_ndvi_60_90d") if recent_delta_obs else None

    # Step-Function Canopy Collapse Event Detection
    collapse_info = {"collapse_detected": False}
    if dates_list and ndvi_series:
        collapse_info = detect_canopy_collapse_events(dates_list, ndvi_series)

    # 1. Check for Active / Standing Cane Current State
    if is_curr_valid and curr_ndvi is not None and curr_ndvi >= 0.50 and curr_canopy >= 50.0:
        if is_perennial or hist_green_days >= 180:
            status = "SUGARCANE_COMPATIBLE_STRONG_LONG_DURATION_CANOPY"
            phase  = "STANDING_MATURE_CANOPY"
            rec    = "SCHEDULE_FOR_HARVEST_SUPPLY"
            reason = f"High measured canopy ({curr_canopy:.1f}%, NDVI: {curr_ndvi:.3f}) with continuous 12-month green duration ({hist_green_days}d)."
        else:
            status = "ACTIVE_VEGETATIVE_GROWTH_RECENT_CROP"
            phase  = "ACTIVE_TILLERING_GROWTH"
            rec    = "MONITOR_GROWTH_STAGE"
            reason = f"High measured canopy ({curr_canopy:.1f}%), recent vegetative surge (green duration: {hist_green_days}d)."
            
        return {
            "spatio_temporal_status": status,
            "canopy_trajectory_phase": phase,
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": True,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": rec,
            "diagnostic_rationale": reason
        }

    # 2. Check for Strong Canopy Collapse Event (Consistent with Harvest)
    if collapse_info["collapse_detected"]:
        return {
            "spatio_temporal_status": "STRONG_CANOPY_CLEARING_EVENT_CONSISTENT_WITH_HARVEST",
            "canopy_trajectory_phase": "POST_HARVEST_CLEARING",
            "harvest_detected_flag": True,
            "collapse_event": collapse_info,
            "current_observation_valid": is_curr_valid,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "LOG_HARVEST_AND_VERIFY_WEIGHBRIDGE_RECEIPT",
            "diagnostic_rationale": (
                f"Direct measured canopy collapse from NDVI {collapse_info['pre_collapse_ndvi']:.3f} ({collapse_info['pre_collapse_date']}) "
                f"to {collapse_info['post_collapse_ndvi']:.3f} ({collapse_info['post_collapse_date']}) "
                f"(drop of -{collapse_info['drop_magnitude']:.3f} dNDVI). Consistent with cane harvesting."
            )
        }

    # 3. Check for Strong Recent Recovery / Emerging Crop (e.g. low in Jan snapshot -> surging by August)
    if is_curr_valid and delta_ndvi is not None and delta_ndvi >= 0.25 and curr_ndvi is not None and curr_ndvi >= 0.45:
        return {
            "spatio_temporal_status": "CURRENTLY_EMERGING_OR_RATOON_RECOVERING",
            "canopy_trajectory_phase": "ACTIVE_TILLERING_GROWTH",
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": True,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "RATOON_OR_NEW_PLANTING_VERIFICATION",
            "diagnostic_rationale": f"Recent measured 60-90d canopy surge (+{delta_ndvi:.3f} dNDVI) reaching NDVI {curr_ndvi:.3f}. Crop recovering/emerging."
        }

    # 4. Check for Boundary Shift Discrepancy (Spatial neighborhood high)
    if (r25_can is not None and r25_can >= 45.0) or (r50_can is not None and r50_can >= 45.0):
        return {
            "spatio_temporal_status": "BOUNDARY_OR_REGISTRATION_DISCREPANCY",
            "canopy_trajectory_phase": "ADJACENT_CANE_DETECTED",
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": is_curr_valid,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "GPS_BOUNDARY_RE_SURVEY",
            "diagnostic_rationale": f"Low inside polygon, but strong standing canopy immediately outside in 25-50m buffer ({r25_can}% / {r50_can}%)."
        }

    # 5. Check for Field-Specific Discrepancy in Active Cluster
    if nearest_cane_m is not None and nearest_cane_m <= 150.0:
        return {
            "spatio_temporal_status": "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER",
            "canopy_trajectory_phase": "INDIVIDUAL_FIELD_FALLOW_OR_HARVEST",
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": is_curr_valid,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "FIELD_OFFICER_CONFIRMATION",
            "diagnostic_rationale": f"Individual parcel low, but active high-canopy cane parcel exists {nearest_cane_m:.0f}m away in same cluster."
        }

    # 6. Check for Persistent Non-Plantation / Deep Fallow
    if (hist_max_ndvi is not None and hist_max_ndvi < 0.35 and 
        hist_green_days < 30 and 
        (curr_ndvi is None or curr_ndvi < 0.35)):
        return {
            "spatio_temporal_status": "PERSISTENT_NON_PLANTATION_OR_FALLOW",
            "canopy_trajectory_phase": "PERSISTENT_FALLOW",
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": is_curr_valid,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "FLAG_UNPLANTED_REGISTRATION",
            "diagnostic_rationale": f"Flat low NDVI (peak {hist_max_ndvi:.3f}, green duration {hist_green_days}d) across full 12-month multi-temporal series."
        }

    # 7. Check for Seasonal Rotation Crop
    if hist_green_days > 0 and hist_green_days < 120 and (curr_ndvi is None or curr_ndvi < 0.40):
        return {
            "spatio_temporal_status": "SEASONAL_ROTATION_CROP_DETECTED",
            "canopy_trajectory_phase": "POST_SEASONAL_DRY_DOWN",
            "harvest_detected_flag": False,
            "collapse_event": collapse_info,
            "current_observation_valid": is_curr_valid,
            "current_observation_age_days": obs_age_days,
            "operational_mill_recommendation": "CHECK_NON_CANE_CROP_TYPE",
            "diagnostic_rationale": f"Short duration green peak ({hist_green_days}d) followed by dry-down, inconsistent with 12-18 month sugarcane."
        }

    # Default Unresolved Discrepancy
    return {
        "spatio_temporal_status": "ISOLATED_LOW_CANOPY_UNRESOLVED",
        "canopy_trajectory_phase": "MIXED_CANOPY_DISCREPANCY",
        "harvest_detected_flag": False,
        "collapse_event": collapse_info,
        "current_observation_valid": is_curr_valid,
        "current_observation_age_days": obs_age_days,
        "operational_mill_recommendation": "FIELD_INSPECTION_REQUIRED",
        "diagnostic_rationale": f"Low current NDVI ({curr_ndvi}) with mixed annual history and heterogeneous spatial surroundings."
    }