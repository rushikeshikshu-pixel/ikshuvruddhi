"""
ml/crop_distinction.py
Multi-Crop Phenological Discrimination & Probabilistic Crop Type Classifier
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
    sar_vh_db: Optional[float] = None
) -> Dict[str, Any]:
    """
    Classifies crop type using multi-temporal trajectory parameters and multi-spectral water/RedEdge metrics.
    """
    valid_count = pheno_features.get("valid_observations_count", 0)
    span_days   = pheno_features.get("observation_span_days", 0)
    green_days  = pheno_features.get("green_duration_days", 0)
    max_ndvi    = pheno_features.get("max_ndvi", 0.0)
    mean_ndvi   = pheno_features.get("mean_ndvi", 0.0)
    min_ndvi    = pheno_features.get("min_ndvi", 0.0)
    lswi_rip    = pheno_features.get("mean_ripening_lswi", 0.0)
    ndre_rip    = pheno_features.get("mean_ripening_ndre", 0.0)
    sen_rate    = pheno_features.get("senescence_rate_per_day", 0.0)
    norm_auc    = pheno_features.get("normalized_annual_auc", 0.0)

    # 0. Check data sufficiency
    if valid_count < 3 or span_days < 90:
        return {
            "predicted_crop": "INSUFFICIENT_TEMPORAL_DATA",
            "confidence_pct": 0.0,
            "crop_probabilities": {c: 0.0 for c in CROP_CLASSES},
            "reasoning": f"Only {valid_count} observations over {span_days} days (minimum 3 observations over 90 days required)."
        }

    # 1. Fallow / Bare Soil Check
    if max_ndvi < 0.35 or green_days < 30:
        return {
            "predicted_crop": "FALLOW_OR_BARE_SOIL",
            "confidence_pct": 95.0 if max_ndvi < 0.30 else 85.0,
            "crop_probabilities": {
                "SUGARCANE": 0.01,
                "MAIZE_OR_SEASONAL_GRAIN": 0.02,
                "COTTON_OR_SEMI_PERENNIAL": 0.02,
                "BANANA_OR_BROADLEAF_PERENNIAL": 0.00,
                "FALLOW_OR_BARE_SOIL": 0.95
            },
            "reasoning": f"Peak NDVI ({max_ndvi:.3f}) and green duration ({green_days} d) are below crop growth thresholds."
        }

    scores = {
        "SUGARCANE": 0.0,
        "MAIZE_OR_SEASONAL_GRAIN": 0.0,
        "COTTON_OR_SEMI_PERENNIAL": 0.0,
        "BANANA_OR_BROADLEAF_PERENNIAL": 0.0,
        "FALLOW_OR_BARE_SOIL": 0.0
    }

    # Feature 1: Green Season Duration
    if green_days >= 210:
        scores["SUGARCANE"] += 50.0
        # Banana is non-seasonal year-round with high baseline min_ndvi (>0.50)
        if min_ndvi >= 0.50:
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 45.0
        else: # Sugarcane has distinct germination / emergence baseline (min_ndvi < 0.35)
            scores["SUGARCANE"] += 20.0
            scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 15.0
        scores["COTTON_OR_SEMI_PERENNIAL"] -= 10.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] -= 40.0
    elif 120 <= green_days < 210:
        scores["COTTON_OR_SEMI_PERENNIAL"] += 55.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
        scores["SUGARCANE"] -= 10.0
    elif green_days < 120:
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 60.0
        scores["COTTON_OR_SEMI_PERENNIAL"] += 10.0
        scores["SUGARCANE"] -= 35.0

    # Feature 2: Canopy Moisture & Water Retention (LSWI)
    if lswi_rip >= 0.14:
        scores["SUGARCANE"] += 25.0
        scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 20.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] -= 20.0
        scores["COTTON_OR_SEMI_PERENNIAL"] -= 10.0
    elif 0.04 <= lswi_rip < 0.14:
        scores["COTTON_OR_SEMI_PERENNIAL"] += 20.0
        scores["SUGARCANE"] += 5.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
    else: # lswi_rip < 0.04 (dry harvest / senescence)
        if green_days < 120:
            scores["MAIZE_OR_SEASONAL_GRAIN"] += 25.0
        else:
            scores["COTTON_OR_SEMI_PERENNIAL"] += 25.0
        scores["SUGARCANE"] -= 20.0

    # Feature 3: RedEdge Chlorophyll Density (NDRE)
    if ndre_rip >= 0.32:
        scores["SUGARCANE"] += 20.0
        scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 15.0
    elif 0.20 <= ndre_rip < 0.32:
        scores["COTTON_OR_SEMI_PERENNIAL"] += 15.0
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 10.0
    else:
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 15.0
        scores["COTTON_OR_SEMI_PERENNIAL"] += 10.0

    # Feature 4: Normalized Annual AUC
    if norm_auc >= 200.0:
        scores["SUGARCANE"] += 15.0
        scores["BANANA_OR_BROADLEAF_PERENNIAL"] += 15.0
    elif norm_auc < 140.0:
        scores["MAIZE_OR_SEASONAL_GRAIN"] += 15.0
        scores["SUGARCANE"] -= 15.0

    # Feature 5: SAR Radar Structural Backscatter (if available)
    if sar_vh_db is not None:
        if sar_vh_db >= -13.0: # High volume scattering from 3m tall dense stalk canopy
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

    # Softmax with temperature = 8.0 for sharp probabilistic discrimination
    score_keys = list(scores.keys())
    raw_vals = np.array([scores[k] for k in score_keys])
    # Shift by max for numerical stability
    shifted = raw_vals - np.max(raw_vals)
    exp_s = np.exp(shifted / 8.0)
    p_vals = exp_s / np.sum(exp_s)
    probs = {k: round(float(p_vals[i]), 3) for i, k in enumerate(score_keys)}

    predicted_crop = max(probs, key=probs.get)
    confidence = round(probs[predicted_crop] * 100.0, 1)

    reasoning = (
        f"Classified as {predicted_crop} ({confidence}% conf) based on "
        f"Green Duration: {green_days}d (span: {span_days}d), Ripening LSWI: {lswi_rip:.3f}, "
        f"Ripening NDRE: {ndre_rip:.3f}, Normalized AUC: {norm_auc:.1f}."
    )

    return {
        "predicted_crop": predicted_crop,
        "confidence_pct": confidence,
        "crop_probabilities": probs,
        "phenology_summary": {
            "green_duration_days": green_days,
            "observation_span_days": span_days,
            "mean_ripening_lswi": lswi_rip,
            "mean_ripening_ndre": ndre_rip,
            "normalized_annual_auc": norm_auc,
            "is_perennial_profile": pheno_features.get("is_perennial_profile", False)
        },
        "reasoning": reasoning
    }