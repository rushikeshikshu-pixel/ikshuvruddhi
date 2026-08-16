"""
ml/spatio_temporal_engine.py
Unified 3-Layer Spatio-Temporal Intelligence & Crop Lifecycle Decision Engine
Integrates:
  Layer 1: Current State (Latest High-Quality Observation, e.g., August 2026)
  Layer 2: Recent 60-90 Day Delta & Momentum Trajectory
  Layer 3: 12-18 Month Phenological Trajectory & Historical Harvest Collapses
  Layer 4: Concentric Spatial Context Rings (25m, 50m, 100m, 250m) & Cluster Proximity
  Layer 5: Cadastral Registration Metadata (Plantation Date, Variety, Deduplicated Group)
"""

from typing import Dict, Any, List, Optional
import numpy as np

def evaluate_spatio_temporal_profile(
    current_obs: Dict[str, Any],            # {'ndvi': 0.65, 'occupancy_pct': 80.0, 'usability_pct': 95.0, 'date': '2026-08-10'}
    pheno_features: Dict[str, Any],         # Output of extract_phenological_trajectory_features()
    spatial_context: Dict[str, Any],        # Output of diagnose_spatial_discrepancy() & ring_stats
    recent_delta_obs: Optional[Dict[str, Any]] = None, # {'delta_ndvi_60_90d': +0.25, 'days_span': 70}
    cadastral_meta: Optional[Dict[str, Any]] = None    # {'plantation_date': '...', 'variety': '...'}
) -> Dict[str, Any]:
    """
    Synthesizes current observation, recent delta, multi-season history, and spatial neighborhood into an operational diagnosis.
    """
    curr_ndvi = current_obs.get("ndvi")
    curr_occ  = current_obs.get("occupancy_pct", 0.0)
    curr_date = current_obs.get("date", "CURRENT")

    hist_green_days = pheno_features.get("green_duration_days", 0)
    hist_max_ndvi   = pheno_features.get("max_ndvi")
    hist_min_ndvi   = pheno_features.get("min_ndvi")
    hist_sen_rate   = pheno_features.get("senescence_rate_per_day", 0.0)
    hist_auc        = pheno_features.get("normalized_annual_auc", 0.0)
    is_perennial    = pheno_features.get("is_perennial_profile", False)

    spatial_stratum = spatial_context.get("spatial_discrepancy_stratum", "UNKNOWN")
    nearest_cane_m  = spatial_context.get("nearest_high_canopy_dist_m")
    r25_can         = spatial_context.get("ring_25m_canopy_pct")
    r50_can         = spatial_context.get("ring_50m_canopy_pct")

    delta_ndvi = recent_delta_obs.get("delta_ndvi_60_90d") if recent_delta_obs else None

    # 1. Check for Active / Standing Cane Current State
    if curr_ndvi is not None and curr_ndvi >= 0.50 and curr_occ >= 50.0:
        if is_perennial or hist_green_days >= 180:
            status = "SUGARCANE_COMPATIBLE_STRONG_LONG_DURATION_CANOPY"
            phase  = "STANDING_MATURE_CANOPY"
            rec    = "SCHEDULE_FOR_HARVEST_SUPPLY"
            reason = f"High current canopy ({curr_occ:.1f}%, NDVI: {curr_ndvi:.3f}) with continuous 12-month green duration ({hist_green_days}d)."
        else:
            status = "ACTIVE_VEGETATIVE_GROWTH_RECENT_CROP"
            phase  = "ACTIVE_TILLERING_GROWTH"
            rec    = "MONITOR_GROWTH_STAGE"
            reason = f"High current canopy ({curr_occ:.1f}%), recent vegetative surge (green duration: {hist_green_days}d)."
            
        return {
            "spatio_temporal_status": status,
            "canopy_trajectory_phase": phase,
            "harvest_detected_flag": False,
            "operational_mill_recommendation": rec,
            "diagnostic_rationale": reason
        }

    # 2. Check for Strong Recent Recovery / Emerging Crop (e.g. low in Jan snapshot -> surging by August)
    if delta_ndvi is not None and delta_ndvi >= 0.25 and curr_ndvi is not None and curr_ndvi >= 0.45:
        return {
            "spatio_temporal_status": "CURRENTLY_EMERGING_OR_RATOON_RECOVERING",
            "canopy_trajectory_phase": "ACTIVE_TILLERING_GROWTH",
            "harvest_detected_flag": False,
            "operational_mill_recommendation": "RATOON_OR_NEW_PLANTING_VERIFICATION",
            "diagnostic_rationale": f"Recent 60-90d canopy surge (+{delta_ndvi:.3f} dNDVI) reaching NDVI {curr_ndvi:.3f}. Crop recovering/emerging."
        }

    # 3. Check for Harvest Event (High historical canopy -> sudden collapse -> currently low)
    if (hist_max_ndvi is not None and hist_max_ndvi >= 0.55 and 
        hist_sen_rate >= 0.008 and 
        hist_green_days >= 90 and 
        (curr_ndvi is None or curr_ndvi < 0.40)):
        return {
            "spatio_temporal_status": "LIKELY_HARVESTED_CANE_PARCEL",
            "canopy_trajectory_phase": "POST_HARVEST_CLEARING",
            "harvest_detected_flag": True,
            "operational_mill_recommendation": "LOG_HARVEST_COMPLETION",
            "diagnostic_rationale": (
                f"Historical 12-month trajectory reached peak NDVI {hist_max_ndvi:.3f} "
                f"with {hist_green_days}d green duration, followed by sharp canopy collapse "
                f"({hist_sen_rate:.4f} dNDVI/d). Currently in post-harvest stubble/clearing."
            )
        }

    # 4. Check for Boundary Shift Discrepancy (Spatial neighborhood high)
    if (r25_can is not None and r25_can >= 45.0) or (r50_can is not None and r50_can >= 45.0):
        return {
            "spatio_temporal_status": "BOUNDARY_OR_REGISTRATION_DISCREPANCY",
            "canopy_trajectory_phase": "ADJACENT_CANE_DETECTED",
            "harvest_detected_flag": False,
            "operational_mill_recommendation": "GPS_BOUNDARY_RE_SURVEY",
            "diagnostic_rationale": f"Low inside polygon, but strong standing canopy immediately outside in 25-50m buffer ({r25_can}% / {r50_can}%)."
        }

    # 5. Check for Field-Specific Harvest in Active Cluster
    if nearest_cane_m is not None and nearest_cane_m <= 150.0:
        return {
            "spatio_temporal_status": "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER",
            "canopy_trajectory_phase": "INDIVIDUAL_FIELD_FALLOW_OR_HARVEST",
            "harvest_detected_flag": True if hist_sen_rate >= 0.006 else False,
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
            "operational_mill_recommendation": "FLAG_UNPLANTED_REGISTRATION",
            "diagnostic_rationale": f"Flat low NDVI (peak {hist_max_ndvi:.3f}, green duration {hist_green_days}d) across full 12-month multi-temporal series."
        }

    # 7. Check for Seasonal Rotation Crop
    if hist_green_days > 0 and hist_green_days < 120 and (curr_ndvi is None or curr_ndvi < 0.40):
        return {
            "spatio_temporal_status": "SEASONAL_ROTATION_CROP_DETECTED",
            "canopy_trajectory_phase": "POST_SEASONAL_DRY_DOWN",
            "harvest_detected_flag": False,
            "operational_mill_recommendation": "CHECK_NON_CANE_CROP_TYPE",
            "diagnostic_rationale": f"Short duration green peak ({hist_green_days}d) followed by dry-down, inconsistent with 12-18 month sugarcane."
        }

    # Default Unresolved Discrepancy
    return {
        "spatio_temporal_status": "ISOLATED_LOW_CANOPY_UNRESOLVED",
        "canopy_trajectory_phase": "MIXED_CANOPY_DISCREPANCY",
        "harvest_detected_flag": False,
        "operational_mill_recommendation": "FIELD_INSPECTION_REQUIRED",
        "diagnostic_rationale": f"Low current NDVI ({curr_ndvi}) with mixed annual history and heterogeneous spatial surroundings."
    }