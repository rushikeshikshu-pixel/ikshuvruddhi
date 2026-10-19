# -*- coding: utf-8 -*-
"""
Unit Tests for Biophysical Ripening Cadence Engine & Dual-Track Satellite Monitoring
=====================================================================================
Tests:
1. Track A: 5-Day Anomaly Detection & Unauthorized Diversion Trigger.
2. Track B: 14-Day Ripening Projection & Biophysical Rate Bounds:
   - Active Ripening: +0.035 to +0.055 °Bx/day (+0.50 to +0.80 °Bx / 14d, max +1.50 °Bx/month).
   - Peak Maturity Plateau: net change 0.00 ± 0.02 °Bx/day (Top-to-Bottom Brix ratio 0.95–1.00).
   - Post-Maturity Inversion: Pol loss -0.04 to -0.10 %/day (> 480d Adsali, > 375d Suru, purity < 80%).
3. Biophysical Event Triggers:
   - Chilling nights (Tmin <= 15°C, diurnal range >= 14°C).
   - Pre-harvest drying-off (15d delta NDWI <= -0.08 without rain).
   - GDD thermal gate (delta GDD >= 120 °C-days).
   - Arrowing / Flowering detection (NDRE drop <= -0.05 with SWIR spike -> 60-75d countdown).
4. Varietal Curves:
   - Co-86032 (early accumulator, 60-90d stable plateau).
   - CoM-0265 (heavy biomass, late sugar accumulation, needs 13+ months / 390+ days).
"""

import pytest
import datetime
from ml.biophysical_ripening_cadence import (
    BiophysicalRipeningCadenceEngine,
    detect_5day_anomaly,
    check_inversion_risk,
    evaluate_chilling_trigger,
    evaluate_drying_off_trigger,
    evaluate_gdd_thermal_gate,
    detect_arrowing,
    project_14day_ripening,
    run_dual_track_cadence,
    calculate_crop_age_days,
    calculate_ccs,
    calculate_purity,
    ACTIVE_BRIX_MIN_PER_DAY,
    ACTIVE_BRIX_MAX_PER_DAY,
    ACTIVE_BRIX_14D_MIN,
    ACTIVE_BRIX_14D_MAX,
    MAX_BRIX_PER_MONTH,
    PLATEAU_BRIX_DELTA_MIN,
    PLATEAU_BRIX_DELTA_MAX,
    PLATEAU_TOP_BOTTOM_RATIO_MIN,
    PLATEAU_TOP_BOTTOM_RATIO_MAX,
    INVERSION_POL_LOSS_MIN_PER_DAY,
    INVERSION_POL_LOSS_MAX_PER_DAY,
    INVERSION_AGE_DAYS_ADSALI,
    INVERSION_AGE_DAYS_SURU,
    EMERGENCY_HARVEST_MIN_DAYS,
    EMERGENCY_HARVEST_MAX_DAYS
)


# ============================================================================
# 1. 5-DAY ANOMALY & DIVERSION DETECTION
# ============================================================================

class TestFiveDayAnomalyDetection:
    """Verifies 5-day cadence detecting sudden canopy collapse and diversion."""

    def test_sudden_canopy_collapse_detected(self):
        """NDVI drops > 0.35 in 5 days must trigger critical diversion alert."""
        res = detect_5day_anomaly(
            current_ndvi=0.38,
            previous_ndvi=0.78,
            interval_days=5.0
        )
        assert res["anomaly_detected"] is True
        assert res["event_type"] == "UNAUTHORIZED_HARVEST_OR_DIVERSION"
        assert res["severity"] == "CRITICAL"
        assert res["drop_magnitude"] == pytest.approx(0.40, abs=1e-3)
        assert res["delta_ndvi"] == pytest.approx(-0.40, abs=1e-3)
        assert "Sudden canopy collapse detected" in res["alert_message"]

    def test_normal_canopy_not_flagged(self):
        """Normal vegetative growth or slight change should not trigger anomaly."""
        res = detect_5day_anomaly(
            current_ndvi=0.74,
            previous_ndvi=0.76,
            interval_days=5.0
        )
        assert res["anomaly_detected"] is False
        assert res["event_type"] == "NORMAL_CANOPY"
        assert res["severity"] == "NOMINAL"
        assert res["drop_magnitude"] == pytest.approx(0.02, abs=1e-3)

    def test_vegetative_vigor_increase_not_flagged(self):
        """Canopy growth (positive delta NDVI) is nominal."""
        res = detect_5day_anomaly(
            current_ndvi=0.82,
            previous_ndvi=0.75,
            interval_days=5.0
        )
        assert res["anomaly_detected"] is False
        assert res["drop_magnitude"] == 0.0

    def test_interval_scaling(self):
        """Drop of 0.30 over 3.5 days scales to > 0.35 equivalent over 5 days."""
        res = detect_5day_anomaly(
            current_ndvi=0.40,
            previous_ndvi=0.70,
            interval_days=3.5
        )
        assert res["effective_5d_drop"] > 0.35
        assert res["anomaly_detected"] is True

    def test_high_starting_ndvi_collapse_detected(self):
        """NDVI drop of 0.40 (0.86 to 0.46) must trigger anomaly even if current_ndvi >= 0.45."""
        res = detect_5day_anomaly(
            current_ndvi=0.46,
            previous_ndvi=0.86,
            interval_days=5.0
        )
        assert res["anomaly_detected"] is True
        assert res["event_type"] == "UNAUTHORIZED_HARVEST_OR_DIVERSION"
        assert res["severity"] == "CRITICAL"

    def test_ndre_collapse_triggers_anomaly(self):
        """Severe NDRE collapse (delta <= -0.20) with significant NDVI drop triggers anomaly."""
        res = detect_5day_anomaly(
            current_ndvi=0.50,
            previous_ndvi=0.78,
            interval_days=5.0,
            current_ndre=0.30,
            previous_ndre=0.55
        )
        assert res["ndre_collapsed"] is True
        assert res["anomaly_detected"] is True


# ============================================================================
# 2. 14-DAY RIPENING PROJECTION & BIOPHYSICAL BOUNDARIES
# ============================================================================

class TestFourteenDayRipeningCadence:
    """Verifies 14-day rolling window projection against biophysical dynamics."""

    def test_active_ripening_suru_boundaries(self):
        """Suru at month 10 (300 days) must accumulate within +0.035 to +0.055 °Bx/day."""
        proj = project_14day_ripening(
            current_brix=17.5,
            current_pol=14.5,
            crop_age_days=300.0,
            cane_type="SURU",
            variety="CO 86032",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "ACTIVE_RIPENING"
        assert proj["velocity"] == "ACCUMULATION"

        daily_rate = proj["daily_rates"]["brix_per_day"]
        assert ACTIVE_BRIX_MIN_PER_DAY <= daily_rate <= ACTIVE_BRIX_MAX_PER_DAY

        delta_14d_brix = proj["delta_projection"]["delta_brix"]
        assert ACTIVE_BRIX_14D_MIN <= delta_14d_brix <= ACTIVE_BRIX_14D_MAX

        # Check monthly physiological ceiling: 30 days must never exceed +1.50 °Bx/month
        monthly_extrapolation = daily_rate * 30.0
        assert monthly_extrapolation <= MAX_BRIX_PER_MONTH + 0.15

        # Check positive sugar gains
        assert proj["delta_projection"]["delta_ccs"] > 0
        assert proj["delta_projection"]["delta_pol"] > 0
        assert proj["projected"]["brix"] > proj["initial"]["brix"]

    def test_active_ripening_adsali_boundaries(self):
        """Adsali at month 13 (395 days) must accumulate within +0.035 to +0.055 °Bx/day."""
        proj = project_14day_ripening(
            current_brix=16.8,
            current_pol=13.8,
            crop_age_days=395.0,
            cane_type="ADSALI",
            variety="DEFAULT",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "ACTIVE_RIPENING"
        daily_rate = proj["daily_rates"]["brix_per_day"]
        assert ACTIVE_BRIX_MIN_PER_DAY <= daily_rate <= ACTIVE_BRIX_MAX_PER_DAY
        delta_14d_brix = proj["delta_projection"]["delta_brix"]
        assert ACTIVE_BRIX_14D_MIN <= delta_14d_brix <= ACTIVE_BRIX_14D_MAX

    def test_peak_maturity_plateau_suru(self):
        """Suru at month 11.5 (350 days) reaches peak plateau: net change 0.00 ± 0.02 °Bx/day."""
        proj = project_14day_ripening(
            current_brix=20.5,
            current_pol=18.0,
            crop_age_days=350.0,
            cane_type="SURU",
            variety="CO 86032",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "PEAK_MATURITY_PLATEAU"
        assert proj["velocity"] == "PLATEAU"
        daily_rate = proj["daily_rates"]["brix_per_day"]
        assert PLATEAU_BRIX_DELTA_MIN <= daily_rate <= PLATEAU_BRIX_DELTA_MAX

        # Top-to-bottom Brix ratio reaches 0.95–1.00 at plateau
        ratio = proj["top_to_bottom_brix_ratio"]
        assert PLATEAU_TOP_BOTTOM_RATIO_MIN <= ratio <= PLATEAU_TOP_BOTTOM_RATIO_MAX

    def test_peak_maturity_plateau_adsali(self):
        """Adsali at month 15.5 (470 days) reaches peak plateau."""
        proj = project_14day_ripening(
            current_brix=21.0,
            current_pol=18.5,
            crop_age_days=470.0,
            cane_type="ADSALI",
            variety="DEFAULT",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "PEAK_MATURITY_PLATEAU"
        assert proj["velocity"] == "PLATEAU"
        daily_rate = proj["daily_rates"]["brix_per_day"]
        assert PLATEAU_BRIX_DELTA_MIN <= daily_rate <= PLATEAU_BRIX_DELTA_MAX
        assert PLATEAU_TOP_BOTTOM_RATIO_MIN <= proj["top_to_bottom_brix_ratio"] <= PLATEAU_TOP_BOTTOM_RATIO_MAX

    def test_post_maturity_inversion_by_age_suru(self):
        """Suru crop_age_days > 375 must trigger post-maturity inversion."""
        proj = project_14day_ripening(
            current_brix=20.0,
            current_pol=16.0,
            crop_age_days=390.0,  # > 375 days
            cane_type="SURU",
            variety="DEFAULT",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "POST_MATURITY_INVERSION"
        assert proj["velocity"] == "INVERSION"
        assert proj["inversion_risk"]["is_inversion"] is True

        # Pol loss rate must be within -0.04 to -0.10 %/day
        pol_daily_rate = proj["daily_rates"]["pol_per_day"]
        assert INVERSION_POL_LOSS_MIN_PER_DAY <= pol_daily_rate <= INVERSION_POL_LOSS_MAX_PER_DAY

        # 14-day Pol delta must be negative (-0.56 to -1.40 % Pol)
        delta_pol_14d = proj["delta_projection"]["delta_pol"]
        assert delta_pol_14d <= -0.50
        assert proj["delta_projection"]["delta_ccs"] < 0

    def test_post_maturity_inversion_by_age_adsali(self):
        """Adsali crop_age_days > 480 must trigger post-maturity inversion."""
        proj = project_14day_ripening(
            current_brix=21.0,
            current_pol=16.5,
            crop_age_days=495.0,  # > 480 days
            cane_type="ADSALI",
            variety="DEFAULT",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "POST_MATURITY_INVERSION"
        assert proj["velocity"] == "INVERSION"
        assert proj["inversion_risk"]["is_inversion"] is True
        assert proj["inversion_risk"]["crop_age_days"] == 495.0

    def test_post_maturity_inversion_by_low_purity(self):
        """Juice purity < 80% triggers inversion in mature cane (age >= min maturity age)."""
        # Pol 13.0, Brix 18.0 -> purity = 72.2% (< 80%) in 310d mature Suru
        proj = project_14day_ripening(
            current_brix=18.0,
            current_pol=13.0,
            crop_age_days=310.0,
            cane_type="SURU",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "POST_MATURITY_INVERSION"
        assert proj["inversion_risk"]["purity_low"] is True
        assert proj["delta_projection"]["delta_pol"] < 0

    def test_immature_crop_low_purity_not_inversion(self):
        """Immature cane (200 days old) with low purity (66.7%) is VEGETATIVE, not post-maturity inversion."""
        proj = project_14day_ripening(
            current_brix=12.0,
            current_pol=8.0,
            crop_age_days=200.0,
            cane_type="SURU",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "VEGETATIVE"
        assert proj["velocity"] == "VEGETATIVE"
        assert proj["inversion_risk"]["is_inversion"] is False
        assert "VEGETATIVE_HOLD" in proj["harvest_advisory"]

    def test_young_adsali_in_vegetative_stage(self):
        """Adsali at 280 days (month 9) is in VEGETATIVE stage; active ripening starts at month 12 (365d)."""
        proj = project_14day_ripening(
            current_brix=14.0,
            current_pol=11.5,
            crop_age_days=280.0,
            cane_type="ADSALI",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "VEGETATIVE"
        assert proj["velocity"] == "VEGETATIVE"

    def test_young_com0265_in_vegetative_stage(self):
        """CoM-0265 at 280 days is in heavy biomass VEGETATIVE stage; requires 13+ months (390+ days)."""
        proj = project_14day_ripening(
            current_brix=13.5,
            current_pol=11.0,
            crop_age_days=280.0,
            cane_type="SURU",
            variety="COM 0265",
            cadence_days=14
        )
        assert proj["physiological_phase"] == "VEGETATIVE"
        assert proj["velocity"] == "VEGETATIVE"


# ============================================================================
# 3. BIOPHYSICAL EVENT TRIGGERS
# ============================================================================

class TestBiophysicalEventTriggers:
    """Verifies chilling nights, drying-off, GDD thermal gate, and arrowing."""

    def test_chilling_nights_active(self):
        """Tmin <= 15°C and diurnal range >= 14°C accelerates ripening."""
        trig = evaluate_chilling_trigger(tmin=13.5, tmax=28.5)
        assert trig["active"] is True
        assert trig["diurnal_range"] == 15.0
        assert trig["acceleration_factor"] > 1.0

        # Run projection with chilling nights -> daily Brix rate pushes towards 0.055
        proj = project_14day_ripening(
            current_brix=17.0,
            current_pol=14.0,
            crop_age_days=300.0,
            cane_type="SURU",
            tmin=13.5,
            tmax=28.5,
            cadence_days=14
        )
        assert proj["triggers"]["chilling_nights"]["active"] is True
        assert proj["daily_rates"]["brix_per_day"] >= 0.050
        # Under chilling night conditions, 14-day delta Brix accelerates towards upper bound (+0.50 to +0.80)
        assert proj["delta_projection"]["delta_brix"] >= 0.75
        assert proj["delta_projection"]["delta_brix"] <= 0.80

    def test_chilling_nights_inactive(self):
        """Warm nights (Tmin = 21°C) do not trigger chilling acceleration."""
        trig = evaluate_chilling_trigger(tmin=21.0, tmax=31.0)
        assert trig["active"] is False

    def test_preharvest_drying_off_active(self):
        """15-day delta NDWI <= -0.08 without rain locks in sucrose."""
        trig = evaluate_drying_off_trigger(delta_ndwi_15d=-0.09, rainfall_15d_mm=0.0)
        assert trig["active"] is True
        assert trig["purity_boost"] > 0

    def test_preharvest_drying_off_void_by_rain(self):
        """Rainfall > 5mm cancels drying-off trigger even if NDWI dropped."""
        trig = evaluate_drying_off_trigger(delta_ndwi_15d=-0.10, rainfall_15d_mm=25.0)
        assert trig["active"] is False

    def test_gdd_thermal_gate(self):
        """Delta GDD >= 120 °C-days passes gate; < 120 °C-days dampens accumulation."""
        gate_open = evaluate_gdd_thermal_gate(delta_gdd=135.0)
        assert gate_open["gate_passed"] is True
        assert gate_open["thermal_multiplier"] == 1.0

        gate_closed = evaluate_gdd_thermal_gate(delta_gdd=75.0)
        assert gate_closed["gate_passed"] is False
        assert gate_closed["thermal_multiplier"] < 1.0

    def test_arrowing_flowering_detection(self):
        """RedEdge NDRE drop (<= -0.05) with SWIR spike triggers 60-75d countdown."""
        arrow = detect_arrowing(delta_ndre=-0.07, swir_spike=True)
        assert arrow["arrowing_detected"] is True
        assert arrow["emergency_harvest_window_days"] == (EMERGENCY_HARVEST_MIN_DAYS, EMERGENCY_HARVEST_MAX_DAYS)
        assert arrow["emergency_harvest_deadline_days"] == 75
        assert "Arrowing/Flowering detected" in arrow["alert_message"]

    def test_no_arrowing_without_swir_spike(self):
        """NDRE drop alone without SWIR spike is not arrowing."""
        arrow = detect_arrowing(delta_ndre=-0.06, swir_spike=False, delta_swir=0.01)
        assert arrow["arrowing_detected"] is False


# ============================================================================
# 4. VARIETAL PROFILES (Co-86032 vs CoM-0265)
# ============================================================================

class TestVarietalProfiles:
    """Verifies physiological curve differences between benchmark and heavy biomass varieties."""

    def test_co_86032_profile(self):
        """Co-86032 is an early accumulator with a stable 60-90 day plateau."""
        proj = project_14day_ripening(
            current_brix=19.5,
            current_pol=17.2,
            crop_age_days=340.0,
            cane_type="SURU",
            variety="CO 86032"
        )
        assert proj["variety_code"] == "CO 86032"
        assert "Co-86032" in proj["variety"]
        # Inversion susceptibility is low, stable plateau
        inv = check_inversion_risk(crop_age_days=360, cane_type="SURU", variety="CO 86032")
        assert inv["is_inversion"] is False

    def test_com_0265_delayed_ripening_requirement(self):
        """CoM-0265 needs 13+ months (390+ days) before reaching peak sucrose."""
        # At 320 days, CoM-0265 should be slower in sucrose accumulation
        proj_young = project_14day_ripening(
            current_brix=16.0,
            current_pol=13.0,
            crop_age_days=320.0,
            cane_type="SURU",
            variety="COM 0265"
        )
        assert proj_young["variety_code"] == "COM 0265"

        # At 400 days (13+ months), CoM-0265 enters peak maturity plateau
        proj_mature = project_14day_ripening(
            current_brix=20.0,
            current_pol=17.5,
            crop_age_days=400.0,
            cane_type="SURU",
            variety="COM 0265"
        )
        assert proj_mature["physiological_phase"] == "PEAK_MATURITY_PLATEAU"

    def test_com_0265_inversion_age_threshold(self):
        """CoM-0265 inversion age is > 430 days (unlike standard Suru > 375 days)."""
        inv_plateau = check_inversion_risk(crop_age_days=410, cane_type="SURU", variety="COM 0265")
        assert inv_plateau["is_inversion"] is False

        inv_overmature = check_inversion_risk(crop_age_days=435, cane_type="SURU", variety="COM 0265")
        assert inv_overmature["is_inversion"] is True
        assert inv_overmature["age_exceeded"] is True


# ============================================================================
# 5. DUAL-TRACK ORCHESTRATION & UTILITIES
# ============================================================================

class TestDualTrackOrchestrator:
    """Tests the unified runner executing Track A and Track B together."""

    def test_unified_run(self):
        dossier = run_dual_track_cadence(
            current_ndvi=0.74,
            previous_ndvi=0.76,
            current_brix=18.2,
            current_pol=15.6,
            crop_age_days=320.0,
            cane_type="SURU",
            variety="CO 86032",
            weather_params={"tmin": 14.0, "tmax": 29.0},
            satellite_indices={"delta_ndwi_15d": -0.085}
        )
        assert dossier["status"] == "SUCCESS"
        assert "track_a_5day_anomaly" in dossier
        assert "track_b_14day_ripening" in dossier
        assert dossier["track_a_5day_anomaly"]["anomaly_detected"] is False
        assert dossier["track_b_14day_ripening"]["physiological_phase"] == "ACTIVE_RIPENING"

    def test_crop_age_calculation(self):
        plant_date = "2025-11-15"
        ref_date = datetime.date(2026, 10, 15)
        age = calculate_crop_age_days(plant_date, ref_date)
        assert age == 334

    def test_crop_age_calculation_edge_cases(self):
        assert calculate_crop_age_days(None) == 0
        assert calculate_crop_age_days("") == 0
        assert calculate_crop_age_days("invalid_date_format") == 0

    def test_crop_age_indian_date_formats(self):
        ref = datetime.date(2026, 10, 15)
        # 15-11-2025 -> 334 days
        assert calculate_crop_age_days("15-11-2025", ref) == 334
        assert calculate_crop_age_days("15/11/2025", ref) == 334

    def test_ccs_formula_consistency(self):
        # Pol 16.0, Brix 19.0 -> CCS = 16.0 - 0.5 * (19.0 - 16.0) = 14.5
        ccs = calculate_ccs(16.0, 19.0)
        assert ccs == 14.5
        purity = calculate_purity(16.0, 19.0)
        assert purity == pytest.approx(84.21, abs=0.01)
