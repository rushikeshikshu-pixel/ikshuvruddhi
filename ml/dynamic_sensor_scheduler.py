"""
ml/dynamic_sensor_scheduler.py
Production Sensor Hierarchy, Inward Parcel Buffering, and Economic Sensor Scheduling Engine

Components:
  1. Inward Parcel Buffering: Removes 5-8m boundary zones to eliminate mixed pixels (roads, canals, weeds).
  2. Dynamic Sensor Escalation: Evaluates V_image = (Uncertainty * Crop Risk) - Cost_image to trigger PlanetScope.
  3. Tiered Multi-Sensor Fusion: Sentinel-2 (backbone) + LISS-4 (opportunistic texture) + Planet (economic escalation).
"""

import math
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import Polygon
import pyproj
from shapely.ops import transform

def buffer_parcel_inward(
    polygon_coords: List[Tuple[float, float]],
    inward_buffer_meters: float = 6.0
) -> Optional[Polygon]:
    """
    Applies an inward buffer (e.g. -6m) to a parcel polygon in UTM coordinates.
    Eliminates border pixels containing bunds, roads, canals, and neighbouring crops.
    """
    if not polygon_coords or len(polygon_coords) < 3:
        return None

    # Transform to UTM Zone 43N (metric) for accurate distance buffering
    wgs84 = pyproj.CRS("EPSG:4326")
    utm43n = pyproj.CRS("EPSG:32643")
    project_to_utm = pyproj.Transformer.from_crs(wgs84, utm43n, always_xy=True).transform
    project_to_wgs = pyproj.Transformer.from_crs(utm43n, wgs84, always_xy=True).transform

    poly_wgs = Polygon(polygon_coords)
    poly_utm = transform(project_to_utm, poly_wgs)

    # Inward buffer (negative distance)
    buffered_utm = poly_utm.buffer(-inward_buffer_meters)

    if buffered_utm.is_empty or buffered_utm.area < 200.0:
        # If parcel is very small (<0.25 acre), reduce buffer to -3m
        buffered_utm = poly_utm.buffer(-3.0)
        if buffered_utm.is_empty:
            return poly_wgs # Fall back to original if too narrow

    # Convert back to WGS84
    buffered_wgs = transform(project_to_wgs, buffered_utm)
    return buffered_wgs

def evaluate_sensor_escalation(
    parcel_acres: float,
    expected_yield_t_ha: float,
    sugar_cane_frp_per_tonne: float = 3400.0,
    cloud_gap_days: int = 15,
    is_in_harvest_window: bool = True,
    current_model_confidence: float = 0.58,
    planet_pass_cost_inr: float = 1200.0
) -> Dict[str, Any]:
    """
    Economic Sensor Scheduling:
      V_image = (Uncertainty * Economic Value at Risk) - Cost_image

    Evaluates whether purchasing a premium commercial high-resolution pass (PlanetScope)
    is justified by the economic risk of a harvest decision error.
    """
    # 1. Total parcel crop value
    hectares = parcel_acres / 2.47105
    total_expected_tonnes = hectares * expected_yield_t_ha
    parcel_crop_value_inr = total_expected_tonnes * sugar_cane_frp_per_tonne

    # 2. Uncertainty score (increases with cloud gaps during the critical harvest window)
    urgency_multiplier = 1.6 if is_in_harvest_window else 0.7
    gap_penalty = min(1.0, (cloud_gap_days / 20.0))
    uncertainty = (1.0 - current_model_confidence) * gap_penalty * urgency_multiplier
    uncertainty = min(max(uncertainty, 0.05), 0.95)

    # 3. Expected economic loss from wrong harvest scheduling (e.g. 8-12% sugar recovery loss / lodging)
    potential_decision_loss_pct = 0.10
    economic_value_at_risk = parcel_crop_value_inr * potential_decision_loss_pct * uncertainty

    # 4. Net Information Value
    v_image = economic_value_at_risk - planet_pass_cost_inr

    should_escalate = (v_image > 0) and (parcel_acres >= 1.5 or is_in_harvest_window)

    tier_assigned = "TIER_3_PREMIUM_PLANETSCOPE_ESCALATION" if should_escalate else "TIER_1_SENTINEL_LISS_BACKBONE"

    return {
        "parcel_acres": parcel_acres,
        "parcel_crop_value_inr": round(parcel_crop_value_inr, 2),
        "uncertainty_score": round(uncertainty, 3),
        "economic_value_at_risk_inr": round(economic_value_at_risk, 2),
        "planet_cost_inr": planet_pass_cost_inr,
        "net_information_value_inr": round(v_image, 2),
        "recommended_tier": tier_assigned,
        "escalate_to_planet": should_escalate,
        "rationale": (
            f"Expected risk reduction (Rs. {round(economic_value_at_risk):,}) exceeds imagery cost (Rs. {planet_pass_cost_inr:,}). Premium pass recommended."
            if should_escalate else
            f"Standard Sentinel-2 / LISS-4 stack provides sufficient certainty. Premium imagery not cost-justified."
        )
    }