"""
ml/crop_distinction.py
Multi-Crop Phenological Discrimination & Heuristic Crop Type Classifier
Distinguishes Sugarcane (12-18 month perennial grass) from Maize (90-110 day seasonal grain),
Cotton (150-180 day semi-perennial), Banana (broadleaf perennial), and Fallow/Bare Soil.
"""

from typing import Dict, Any, List, Optional
import numpy as np

CROP_CLASSES = [
    "SUGARCANE",
    "MAIZE_OR_SEASONAL_GRAIN",
    "COTTON_OR_SEMI_PERENNIAL",
    "BANANA_OR_BROADLEAF_PERENNIAL",
    "FALLOW_OR_BARE_SOIL",
    "INSUFFICIENT_TEMPORAL_DATA"
]

def classify_crop_from_phenology(
    pheno_features: Dict[str, Any],
    sar_vh_db: Optional[float] = None,
    min_observations: int = 5,
    min_span_days: int = 120
) -> Dict[str, Any]:
    """
    Classifies crop type using multi-temporal trajectory parameters and multi-spectral water/RedEdge metrics.
    """
    valid_count = pheno_features.get("valid_observations_count", 0)
    span_days   = pheno_features.get("observation_span_days", 0)
    green_days  = pheno_features.get("green_duration_days", 0)
    max_ndvi    = pheno_features.get("max_ndvi")
    mean_ndvi   = pheno_features.get("mean_ndvi")
    min_ndvi    = pheno_features.get("min_ndvi")
    lswi_rip    = pheno_features.get("mean_ripening_lswi")
    ndre_rip    = pheno_features.get("mean_ripening_ndre")
    sen_rate    = pheno_features.get("senescence_rate_per_day", 0.0)
    norm_auc    = pheno_features.get("normalized_annual_auc", 0.0)

    # 0. Strict Data Sufficiency Gate
    if valid_count < min_observations or span_days < min_span_days or max_ndvi is None:
        return {
            "predicted_crop": "INSUFFICIENT_TEMPORAL_DATA",
            "heuristic_confidence_score": 0.0,
            "heuristic_crop_score_pct": {c: 0.0 for c in CROP_CLASSES},
            "reasoning": f"Data gate failed: {valid_count} observations over {span_days} days (requires >= {min_observations} observations over >= {min_span_days} days)."
        }

    # 1. Fallow / Bare Soil Check
    if max_ndvi < 0.35 or green_days < 30:
        return {
            "predicted_crop": "FALLOW_OR_BARE_SOIL",
            "heuristic_confidence_score": 95.0 if max_ndvi < 0.30 else 85.0,
            "heuristic_crop_score_pct": {
                "SUGARCANE": 0.01,
                "MAIZE_OR_SEASONAL_GRAIN": 0.02,
                "COTTON_OR_SEMI_PERENNIAL": 0.02,
                "BANANA_OR_BROADLEAF_PERENNIAL": 0.00,
                "FALLOW_OR_BARE_SOIL": 0.95
            },
            "reasoning": f"Peak NDVI ({max_ndvi:.3f}) and green duration ({green_days} d) are below vegetative crop thresholds."
        }

    scores = {
        "SUGARCANE": 0.0,
        "MAIZE_OR_SEASONAL_GRAIN": 0.0,
        "COTTON_OR_SEMI_PERENNIAL": 0.0,
        "BANANA_OR_BROADLEAF_PERENNIAL": 0.0,
        "FALLOW_OR_BARE_SOIL": 0.0
    }

    # Feature 1: Green Season Duration & Baseline Profile
    if green_days >= 210:
        if min_ndvi is not None and min_ndvi >= 0.50:
            # Banana: continuous evergreen broadleaf canopy without emergence ramp
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 60.0
            scores["SUGARCANE"] -= 10.0
        else:
            # Sugarcane: germination / emergence phase starts from lower baseline (min_ndvi < 0.40)
            scores["SUGARCANE"] += 55.0
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 10.0
        scores["COTTON_OR_SEMI_PERENNIAL"] -= 15.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] -= 45.0
    elif 120 <= green_days < 210:
        scores["COTTON_OR_SEMI_PERENNIAL"] += 55.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
        scores["SUGARCANE"] -= 10.0
    elif green_days < 120:
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 60.0
        scores["COTTON_OR_SEMI_PERENNIAL"] += 10.0
        scores["SUGARCANE"] -= 35.0

    # Feature 2: Active Senescence Rate (dNDVI / dt)
    if sen_rate >= 0.015:
        # Sharp rapid harvest / dry-down drop (> 0.45 NDVI drop in 30 days)
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 25.0
        scores["COTTON_OR_SEMI_PERENNIAL"] += 10.0
        scores["BANANA_OR_BROADLEAF_PERENNIAL"] -= 25.0
    elif 0.005 <= sen_rate < 0.015:
        # Moderate gradual dry-down
        scores["COTTON_OR_SEMI_PERENNIAL"] += 15.0
        scores["SUGARCANE"] += 10.0
    else: # sen_rate < 0.005 (very stable or gradual)
        if green_days >= 210:
            if min_ndvi is not None and min_ndvi >= 0.50:
                scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 20.0
            else:
                scores["SUGARCANE"] += 15.0

    # Feature 3: Canopy Moisture & Water Retention (LSWI) - If available
    if lswi_rip is not None:
        if lswi_rip >= 0.14:
            scores["SUGARCANE"] += 25.0
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 25.0
            scores["MAIZE_OR_SEASONAL_GRAIN"] -= 20.0
            scores["COTTON_OR_SEMI_PERENNIAL"] -= 10.0
        elif 0.04 <= lswi_rip < 0.14:
            scores["COTTON_OR_SEMI_PERENNIAL"] += 20.0
            scores["SUGARCANE"] += 5.0
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
        else: # lswi_rip < 0.04 (dry senescence)
            if green_days < 120:
                scores["MAIZE_OR_SEASONAL_GRAIN"] += 20.0
            else:
                scores["COTTON_OR_SEMI_PERENNIAL"] += 20.0
            scores["SUGARCANE"] -= 20.0

    # Feature 4: RedEdge Chlorophyll Density (NDRE) - If available
    if ndre_rip is not None:
        if ndre_rip >= 0.32:
            scores["SUGARCANE"] += 20.0
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 15.0
        elif 0.20 <= ndre_rip < 0.32:
            scores["COTTON_OR_SEMI_PERENNIAL"] += 15.0
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
        else:
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 15.0
            scores["COTTON_OR_SEMI_PERENNIAL"] += 10.0

    # Feature 5: Normalized Annual AUC
    if norm_auc >= 200.0:
        if min_ndvi is not None and min_ndvi >= 0.50:
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 20.0
        else:
            scores["SUGARCANE"] += 15.0
    elif norm_auc < 140.0:
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 15.0
        scores["SUGARCANE"] -= 15.0

    # Feature 6: SAR Radar Structural Backscatter - If available
    if sar_vh_db is not None:
        if sar_vh_db >= -13.0:
            scores["SUGARCANE"] += 25.0
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 15.0
            scores["MAIZE_OR_SEASONAL_GRAIN"] -= 25.0
            scores["COTTON_OR_SEMI_PERENNIAL"] -= 15.0
        elif -17.0 <= sar_vh_db < -13.0:
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 15.0
            scores["COTTON_OR_SEMI_PERENNIAL"] += 15.0
            scores["SUGARCANE"] -= 10.0
        else:
            scores["FALLOW_OR_BARE_SOIL"] += 20.0
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 5.0
            scores["SUGARCANE"] -= 25.0

    # Softmax heuristic score scaling
    score_keys = list(scores.keys())
    raw_vals = np.array([scores[k] for k in score_keys])
    shifted = raw_vals - np.max(raw_vals)
    exp_s = np.exp(shifted / 8.0)
    p_vals = exp_s / np.sum(exp_s)
    probs = {k: round(float(p_vals[i]), 3) for i, k in enumerate(score_keys)}

    predicted_crop = max(probs, key=probs.get)
    confidence = round(probs[predicted_crop] * 100.0, 1)

    lswi_str = f"{lswi_rip:.3f}" if lswi_rip is not None else "N/A"
    ndre_str = f"{ndre_rip:.3f}" if ndre_rip is not None else "N/A"
    reasoning = (
        f"Heuristic classification: {predicted_crop} (score: {confidence}%) based on "
        f"Green Duration: {green_days}d (span: {span_days}d, {valid_count} obs), "
        f"Senescence Rate: {sen_rate:.4f} dNDVI/d, Ripening LSWI: {lswi_str}, "
        f"Ripening NDRE: {ndre_str}, Normalized AUC: {norm_auc:.1f}."
    )

    return {
        "predicted_crop": predicted_crop,
        "heuristic_confidence_score": confidence,
        "heuristic_crop_score_pct": probs,
        "phenology_summary": {
            "green_duration_days": green_days,
            "observation_span_days": span_days,
            "valid_observations_count": valid_count,
            "senescence_rate_per_day": sen_rate,
            "mean_ripening_lswi": lswi_rip,
            "mean_ripening_ndre": ndre_rip,
            "normalized_annual_auc": norm_auc,
            "is_perennial_profile": pheno_features.get("is_perennial_profile", False)
        },
        "reasoning": reasoning
    }