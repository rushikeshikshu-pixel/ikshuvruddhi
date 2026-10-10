import sys
import os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from ml.sota_97_fusion_engine import (
    RadarSARDualPolEngine,
    DiurnalTemperatureRipeningEngine,
    SubMeterBoundaryClippingEngine,
    ActiveWeighbridgeFusionPipeline
)


def test_radar_sar_dual_pol_calculation():
    # Mature sugarcane typical C-band values: VH ~ -12.5 dB, VV ~ -7.5 dB
    res = RadarSARDualPolEngine.compute_dual_pol_rvi(sigma_vh_db=-12.5, sigma_vv_db=-7.5)

    assert "sar_dprvi" in res
    assert "sar_cross_ratio_db" in res
    assert "radar_stalk_volume_index" in res
    assert res["sar_cross_ratio_db"] == -5.0  # -12.5 - (-7.5) = -5.0 dB
    assert 0.0 <= res["sar_dprvi"] <= 1.0
    assert res["sar_penetration_status"] == "VALID_STALK_DETECTED"


def test_radar_sar_bare_soil_low_biomass():
    # Bare soil: VH ~ -23.0 dB, VV ~ -10.0 dB (low volume scattering)
    res = RadarSARDualPolEngine.compute_dual_pol_rvi(sigma_vh_db=-23.0, sigma_vv_db=-10.0)
    assert res["sar_cross_ratio_db"] == -13.0
    assert res["sar_penetration_status"] == "LOW_BIOMASS"


def test_diurnal_temperature_ripening_indices():
    # 30 days of typical Maharashtra winter ripening: sunny 32 C day, cold 14 C night
    tmax = [32.0] * 30
    tmin = [14.0] * 30

    res = DiurnalTemperatureRipeningEngine.calculate_ripening_thermal_indices(tmax, tmin)

    assert res["mean_dtr_celsius"] == 18.0
    assert res["cold_night_days_30d"] == 30
    assert res["ideal_ripening_days_30d"] == 30
    assert res["sucrose_thermal_multiplier"] > 1.05


def test_sub_meter_boundary_clipping():
    # ~2.5 acre rectangular plot in Shevgaon
    coords = [
        (75.3100, 19.3400),
        (75.3110, 19.3400),
        (75.3110, 19.3410),
        (75.3100, 19.3410),
        (75.3100, 19.3400)
    ]

    clipped_poly, orig_ha, core_ha = SubMeterBoundaryClippingEngine.clip_parcel_inward(
        coords, inward_buffer_meters=6.0
    )

    assert isinstance(clipped_poly, Polygon)
    assert not clipped_poly.is_empty
    assert core_ha < orig_ha
    assert orig_ha > 0.8
    assert core_ha > 0.5


def test_active_weighbridge_fusion_pipeline_end_to_end():
    # Construct a realistic multi-modal training dataset with all 4 streams
    np.random.seed(42)
    n = 250

    crop_age = np.random.uniform(280, 400, n)
    pure_ndvi = np.random.uniform(0.60, 0.85, n)
    pure_ndre = pure_ndvi * 0.52 + np.random.normal(0, 0.02, n)
    pure_ndwi = np.random.uniform(0.05, 0.25, n)

    # SAR Dual-Pol
    sar_dprvi = np.random.uniform(0.40, 0.80, n)
    sar_cross_ratio = np.random.uniform(-11.0, -7.0, n)
    radar_stalk = np.random.uniform(0.60, 1.20, n)

    # Weather DTR
    mean_dtr = np.random.uniform(12.0, 18.0, n)
    thermal_mult = 1.0 + (mean_dtr - 10.0) * 0.01

    varieties = np.random.choice(["Co-86032", "VSI-08005", "CoM-0265"], n)
    cane_types = np.random.choice(["Plant", "Ratoon-1", "Adsali"], n)

    # Multi-modal physical sugar synthesis
    base_ccs = 10.2 + (crop_age / 360.0) * 1.8 + (pure_ndre * 1.2) + (radar_stalk * 0.5) * thermal_mult
    lab_ccs = np.clip(base_ccs + np.random.normal(0, 0.10, n), 9.0, 14.5)

    df_sample = pd.DataFrame({
        "crop_age_days": crop_age,
        "core_pure_ndvi": pure_ndvi,
        "core_pure_ndre": pure_ndre,
        "core_pure_ndwi": pure_ndwi,
        "sar_dprvi": sar_dprvi,
        "sar_cross_ratio_db": sar_cross_ratio,
        "radar_stalk_volume_index": radar_stalk,
        "mean_dtr_celsius": mean_dtr,
        "sucrose_thermal_multiplier": thermal_mult,
        "variety": varieties,
        "cane_type": cane_types,
        "lab_ccs": lab_ccs
    })

    pipeline = ActiveWeighbridgeFusionPipeline()
    metrics = pipeline.train_and_calibrate(df_sample)

    print("Multi-Modal Fusion Metrics:", metrics)
    assert metrics["accuracy_pct"] >= 97.0
    assert metrics["mape"] <= 3.0
    assert metrics["mae"] <= 0.30
    assert metrics["conformal_95_error_bound_ccs"] <= 0.35

    # Test single-plot inference
    test_plot = {
        "crop_age_days": 345,
        "core_pure_ndvi": 0.76,
        "core_pure_ndre": 0.42,
        "core_pure_ndwi": 0.15,
        "sar_dprvi": 0.68,
        "sar_cross_ratio_db": -8.2,
        "radar_stalk_volume_index": 0.95,
        "mean_dtr_celsius": 16.5,
        "sucrose_thermal_multiplier": 1.08,
        "variety": "Co-86032",
        "cane_type": "Plant"
    }

    pred_res = pipeline.predict_plot(test_plot)
    assert "predicted_ccs_pct" in pred_res
    assert "conformal_interval_95" in pred_res
    assert pred_res["conformal_interval_95"][0] <= pred_res["predicted_ccs_pct"] <= pred_res["conformal_interval_95"][1]
    assert pred_res["margin_of_error_ccs"] <= 0.35
