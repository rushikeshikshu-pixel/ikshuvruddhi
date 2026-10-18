"""Data Quality and Trust Score Engine (DQI) for Sugarcane Agronomy and Factory Crush.

Validates:
1. Spatial Boundary Integrity (Topology, closed rings, area plausibility).
2. Chemical Physics (Pol <= Brix, Purity between 75% and 93%).
3. Satellite Observation Fidelity (Clean coverage %, cloud %, age).
4. Cut-to-Crush Freshness (Inversion filtering).
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional
import math


def evaluate_plot_quality(
    *,
    plot_no: str,
    registered_acres: float,
    gps_acres: Optional[float] = None,
    variety: Optional[str] = None,
    planting_date: Optional[str] = None,
    crop_age_days: Optional[int] = None,
    lab_brix: Optional[float] = None,
    lab_pol: Optional[float] = None,
    lab_recovery: Optional[float] = None,
    obs_cloud_pct: Optional[float] = None,
    obs_ndvi: Optional[float] = None,
    obs_age_days: Optional[int] = None,
    cut_to_crush_hours: Optional[float] = None,
    has_valid_boundary: bool = True,
) -> Dict[str, Any]:
    score = 100
    flags: List[str] = []

    # 1. Agronomic completeness
    if not variety or "unknown" in str(variety).lower():
        score -= 10
        flags.append("VARIETY_UNVERIFIED")

    if not planting_date and crop_age_days is None:
        score -= 15
        flags.append("PLANTING_DATE_MISSING")
    elif crop_age_days is not None and crop_age_days < 180:
        flags.append(f"IMMATURE_CROP ({crop_age_days}d)")

    # 2. Spatial Boundary Check
    if not has_valid_boundary:
        score -= 20
        flags.append("NO_VALID_BOUNDARY_GEOMETRY")

    if gps_acres is not None and registered_acres > 0:
        area_diff_pct = abs(gps_acres - registered_acres) / registered_acres * 100.0
        if area_diff_pct > 25.0:
            score -= 25
            flags.append(f"AREA_DISCREPANCY ({area_diff_pct:.1f}%)")
        elif area_diff_pct > 12.0:
            score -= 10

    # 3. Chemical Laboratory Physics
    purity_pct: Optional[float] = None
    chemical_fatal = False

    if lab_brix is not None and lab_pol is not None:
        if lab_pol > lab_brix:
            score -= 50
            chemical_fatal = True
            flags.append("FATAL_ERROR: Pol cannot exceed Brix")
        elif lab_brix > 0:
            purity_pct = round((lab_pol / lab_brix) * 100.0, 1)
            if purity_pct < 75.0:
                score -= 15
                flags.append(f"LOW_JUICE_PURITY ({purity_pct}%)")
            elif purity_pct > 93.0:
                score -= 15
                flags.append(f"UNUSUALLY_HIGH_PURITY ({purity_pct}%)")
    else:
        score -= 10
        flags.append("LAB_SAMPLE_PENDING")

    # 4. Satellite Fidelity
    if obs_ndvi is not None:
        if obs_cloud_pct is not None and obs_cloud_pct > 30.0:
            score -= 15
            flags.append(f"CLOUD_CONTAMINATED ({obs_cloud_pct:.0f}%)")
        if obs_age_days is not None and obs_age_days > 25:
            score -= 10
            flags.append(f"AGED_SATELLITE_PASS ({obs_age_days}d)")
        if obs_ndvi < 0.20:
            score -= 10
            flags.append(f"LOW_VEGETATIVE_SIGNAL (NDVI {obs_ndvi:.2f})")
    else:
        score -= 15
        flags.append("NO_SATELLITE_OBSERVATION")

    # 5. Freshness
    if cut_to_crush_hours is not None and cut_to_crush_hours > 36.0:
        score -= 20
        flags.append(f"STALE_CANE ({cut_to_crush_hours:.0f}h post-cut)")

    final_score = max(0, min(100, score))
    grade = "A" if final_score >= 85 else "B" if final_score >= 70 else "C"

    return {
        "plot_no": plot_no,
        "trust_score": final_score,
        "quality_grade": grade,
        "purity_pct": purity_pct,
        "flags": flags,
        "eligible_for_harvest": final_score >= 70 and not chemical_fatal,
        "eligible_for_training": final_score >= 85 and not chemical_fatal and lab_pol is not None,
    }
