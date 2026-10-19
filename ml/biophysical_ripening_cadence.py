# -*- coding: utf-8 -*-
"""
Biophysical Sugarcane Ripening Cadence & Dual-Track Monitoring Engine
====================================================================
SatCane AI Engine — Ahilyanagar & Maharashtra Sugar Industry
Calibrated for operational sugarcane physiology in Western Maharashtra.

Dual-Track Architecture:
1. Track A — 5-Day Satellite Anomaly & Diversion Engine:
   - High-frequency 5-day cadence detecting sudden canopy collapse (NDVI drop > 0.35 in 5 days).
   - Identifies unauthorized cutting, cane diversion to jaggery (gur halwais),
     or illicit delivery to competitor mills.

2. Track B — 10-14 Day Rolling Ripening Projection:
   - 14-day rolling window projection for Pol, Brix, and Commercial Cane Sugar (CCS).
   - Strictly bounded by physiological cane dynamics:
     * Active Ripening (months 9–11 Suru/Khodwa, 12–15 Adsali):
       +0.035 to +0.055 °Bx/day (+0.50 to +0.80 °Bx / 14 days, max +1.50 °Bx/month).
     * Peak Maturity Plateau (months 11–12 Suru, 15–17 Adsali):
       net change 0.00 ± 0.02 °Bx/day; Top-to-Bottom Brix ratio reaches 0.95–1.00.
     * Post-Maturity Inversion:
       Pol loss -0.04 to -0.10 %/day (triggered when crop_age_days > 480 for Adsali,
       > 375 for Suru, or juice purity < 80.0%).

3. Biophysical Event Triggers:
   - Chilling Nights: Tmin <= 15°C and diurnal range >= 14°C -> triggers sucrose synthase,
     accelerating ripening accumulation towards the upper bound (+0.055 °Bx/day).
   - Pre-Harvest Drying-Off: 15-day delta NDWI <= -0.08 without rain (<= 5 mm) -> locks in
     sucrose by halting vegetative flush, boosting juice purity.
   - GDD Thermal Gate: delta GDD >= 120 °C-days (Tb = 10°C) -> opens biochemical ripening gate.
   - Arrowing / Flowering Detection: RedEdge NDRE drop (<= -0.05) with SWIR spike ->
     triggers emergency harvest countdown of 60–75 days before pithiness.

4. Varietal Curves:
   - Co-86032 (Nira): Early sucrose accumulator, extended stable 60–90 day plateau.
   - CoM-0265 (Phule 0265): Heavy biomass accumulator, late sucrose accumulation,
     requires 13+ months (390+ days) before reaching peak sucrose.
"""

from __future__ import annotations
import math
import datetime
from typing import Dict, Any, Optional, Tuple, Union, List


# ============================================================================
# BIOPHYSICAL CONSTANTS & PHYSIOLOGICAL BOUNDARIES
# ============================================================================

# Active Ripening Boundaries (daily rates)
ACTIVE_BRIX_MIN_PER_DAY: float = 0.035   # °Bx/day
ACTIVE_BRIX_MAX_PER_DAY: float = 0.055   # °Bx/day
ACTIVE_BRIX_14D_MIN: float = 0.50        # °Bx / 14 days
ACTIVE_BRIX_14D_MAX: float = 0.80        # °Bx / 14 days
MAX_BRIX_PER_MONTH: float = 1.50         # °Bx / month (physiological ceiling)

# Peak Maturity Plateau Boundaries
PLATEAU_BRIX_DELTA_MIN: float = -0.02    # °Bx/day
PLATEAU_BRIX_DELTA_MAX: float = 0.02     # °Bx/day
PLATEAU_TOP_BOTTOM_RATIO_MIN: float = 0.95
PLATEAU_TOP_BOTTOM_RATIO_MAX: float = 1.00

# Post-Maturity Inversion Boundaries
INVERSION_POL_LOSS_MIN_PER_DAY: float = -0.10   # % Pol/day (severe inversion)
INVERSION_POL_LOSS_MAX_PER_DAY: float = -0.04   # % Pol/day (mild inversion)
INVERSION_PURITY_THRESHOLD: float = 80.0        # % juice purity threshold
INVERSION_AGE_DAYS_SURU: float = 375.0          # > 375 days (~12.5 months)
INVERSION_AGE_DAYS_ADSALI: float = 480.0        # > 480 days (~16 months)

# Event Trigger Thresholds
CHILLING_TMIN_MAX: float = 15.0          # °C
CHILLING_DTR_MIN: float = 14.0           # °C diurnal temperature range
DRYING_OFF_NDWI_DROP: float = -0.08      # 15-day delta NDWI <= -0.08
DRYING_OFF_MAX_RAIN_MM: float = 5.0      # mm rainfall over 15-day window
GDD_THERMAL_GATE_MIN: float = 120.0      # °C-days over 14-day window
GDD_BASE_TEMP: float = 10.0              # °C base temperature for sugarcane
ARROWING_NDRE_DROP_THRESHOLD: float = -0.05
ARROWING_SWIR_SPIKE_RATIO: float = 1.15
EMERGENCY_HARVEST_MIN_DAYS: int = 60
EMERGENCY_HARVEST_MAX_DAYS: int = 75

# 5-Day Canopy Collapse Anomaly
CANOPY_COLLAPSE_NDVI_DROP: float = 0.35  # NDVI drop > 0.35 in 5 days


# ============================================================================
# VARIETAL MATURATION PROFILES
# ============================================================================

VARIETAL_PROFILES: Dict[str, Dict[str, Any]] = {
    'CO 86032': {
        'code': 'CO 86032',
        'name': 'Co-86032 (Nira)',
        'type': 'EARLY_ACCUMULATOR',
        'optimal_plateau_days': 75,
        'plateau_duration_min': 60,
        'plateau_duration_max': 90,
        'early_accumulation_rate': 1.10,
        'min_maturity_months_suru': 11.0,
        'min_maturity_days_suru': 335,
        'min_maturity_months_adsali': 15.0,
        'min_maturity_days_adsali': 455,
        'inversion_susceptibility': 'LOW',
        'biomass_tonnage_potential': 'MODERATE_HIGH',
        'description': 'Benchmark Maharashtra variety; early sucrose accumulator with an extended stable 60–90 day peak plateau.'
    },
    'COM 0265': {
        'code': 'COM 0265',
        'name': 'CoM-0265 (Phule 0265)',
        'type': 'HEAVY_BIOMASS_LATE',
        'optimal_plateau_days': 40,
        'plateau_duration_min': 30,
        'plateau_duration_max': 45,
        'early_accumulation_rate': 0.85,
        'min_maturity_months_suru': 13.0,
        'min_maturity_days_suru': 395,
        'min_maturity_months_adsali': 16.5,
        'min_maturity_days_adsali': 500,
        'inversion_susceptibility': 'HIGH_POST_PEAK',
        'biomass_tonnage_potential': 'VERY_HIGH',
        'description': 'Heavy biomass variety with late sucrose accumulation; requires 13+ months (390+ days) before peak maturity.'
    },
    'MS 10001': {
        'code': 'MS 10001',
        'name': 'MS-10001 (Phule 10001)',
        'type': 'MID_LATE',
        'optimal_plateau_days': 60,
        'plateau_duration_min': 45,
        'plateau_duration_max': 65,
        'early_accumulation_rate': 1.00,
        'min_maturity_months_suru': 11.5,
        'min_maturity_days_suru': 345,
        'min_maturity_months_adsali': 15.5,
        'min_maturity_days_adsali': 465,
        'inversion_susceptibility': 'MODERATE',
        'biomass_tonnage_potential': 'HIGH',
        'description': 'Mid-late maturing variety with steady sucrose accumulation.'
    },
    'CO 11015': {
        'code': 'CO 11015',
        'name': 'Co-11015',
        'type': 'VERY_EARLY',
        'optimal_plateau_days': 60,
        'plateau_duration_min': 50,
        'plateau_duration_max': 70,
        'early_accumulation_rate': 1.18,
        'min_maturity_months_suru': 10.0,
        'min_maturity_days_suru': 305,
        'min_maturity_months_adsali': 14.0,
        'min_maturity_days_adsali': 425,
        'inversion_susceptibility': 'MODERATE',
        'biomass_tonnage_potential': 'MODERATE',
        'description': 'Very early high-sugar accumulator.'
    },
    'DEFAULT': {
        'code': 'DEFAULT',
        'name': 'Standard Maharashtra Cane',
        'type': 'STANDARD',
        'optimal_plateau_days': 60,
        'plateau_duration_min': 45,
        'plateau_duration_max': 60,
        'early_accumulation_rate': 1.00,
        'min_maturity_months_suru': 11.0,
        'min_maturity_days_suru': 335,
        'min_maturity_months_adsali': 15.0,
        'min_maturity_days_adsali': 455,
        'inversion_susceptibility': 'MODERATE',
        'biomass_tonnage_potential': 'MODERATE',
        'description': 'Default Maharashtra seasonal profile.'
    }
}


def normalize_variety_name(variety: Optional[str]) -> str:
    """Normalizes variety string to standard dictionary key."""
    if not variety:
        return 'DEFAULT'
    v = str(variety).upper().replace('-', ' ').replace('_', ' ').strip()
    if '86032' in v:
        return 'CO 86032'
    if '265' in v or '0265' in v:
        return 'COM 0265'
    if '10001' in v:
        return 'MS 10001'
    if '11015' in v:
        return 'CO 11015'
    return 'DEFAULT'


def calculate_crop_age_days(
    plantation_date: Optional[Union[str, datetime.date, datetime.datetime]],
    reference_date: Optional[Union[str, datetime.date, datetime.datetime]] = None
) -> int:
    """Calculates crop age in days between plantation_date and reference_date."""
    if not plantation_date:
        return 0

    def _parse(val: Optional[Union[str, datetime.date, datetime.datetime]]) -> Optional[datetime.date]:
        if val is None:
            return None
        if isinstance(val, datetime.datetime):
            return val.date()
        if isinstance(val, datetime.date):
            return val
        s = str(val).strip()
        if not s:
            return None
        # Handle ISO format 'YYYY-MM-DD' and Indian formats 'DD-MM-YYYY', 'DD/MM/YYYY'
        for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%d-%m-%Y', '%d/%m/%Y'):
            try:
                return datetime.datetime.strptime(s[:10], fmt).date()
            except ValueError:
                pass
        try:
            return datetime.date.fromisoformat(s[:10])
        except Exception:
            return None

    p_date = _parse(plantation_date)
    if p_date is None:
        return 0
    r_date = _parse(reference_date) if reference_date is not None else datetime.date.today()
    if r_date is None:
        r_date = datetime.date.today()
    delta = (r_date - p_date).days
    return max(0, delta)


def calculate_ccs(pol: float, brix: float) -> float:
    """
    Standard Commercial Cane Sugar (CCS %) calculation:
    CCS = Pol - 0.5 * (Brix - Pol) = 1.5 * Pol - 0.5 * Brix
    """
    if brix <= 0:
        return 0.0
    ccs = pol - 0.5 * (brix - pol)
    return round(max(0.0, ccs), 2)


def calculate_purity(pol: float, brix: float) -> float:
    """Juice Purity % = (Pol / Brix) * 100."""
    if brix <= 0:
        return 0.0
    return round(min(100.0, max(0.0, (pol / brix) * 100.0)), 2)


# ============================================================================
# BIOPHYSICAL RIPENING CADENCE ENGINE CLASS
# ============================================================================

class BiophysicalRipeningCadenceEngine:
    """
    Core engine providing dual-track satellite cadence and biophysical ripening projections.
    """

    # ------------------------------------------------------------------------
    # Track A: 5-Day Anomaly & Diversion Engine
    # ------------------------------------------------------------------------
    @classmethod
    def detect_5day_anomaly(
        cls,
        current_ndvi: float,
        previous_ndvi: float,
        interval_days: float = 5.0,
        threshold_drop: float = CANOPY_COLLAPSE_NDVI_DROP,
        current_ndre: Optional[float] = None,
        previous_ndre: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Fast 5-Day Anomaly Detection: Checks for sudden canopy collapse
        (NDVI drop > 0.35 over 5 days) indicating unauthorized harvest or cane diversion.
        """
        delta_ndvi = current_ndvi - previous_ndvi
        drop_magnitude = -delta_ndvi if delta_ndvi < 0 else 0.0

        # Normalize drop if interval deviates slightly from 5 days
        effective_drop = drop_magnitude
        if interval_days > 0 and abs(interval_days - 5.0) > 0.5:
            # Scale to 5-day equivalent
            effective_drop = drop_magnitude * (5.0 / interval_days)

        ndre_collapsed = False
        delta_ndre = 0.0
        if current_ndre is not None and previous_ndre is not None:
            delta_ndre = current_ndre - previous_ndre
            if delta_ndre <= -0.20:
                ndre_collapsed = True

        collapse_detected = (effective_drop >= threshold_drop) or (ndre_collapsed and effective_drop >= 0.25)

        if collapse_detected:
            event_type = "UNAUTHORIZED_HARVEST_OR_DIVERSION"
            severity = "CRITICAL"
            alert_message = (
                f"Sudden canopy collapse detected: NDVI dropped {drop_magnitude:.2f} "
                f"in {interval_days:.1f} days (threshold > {threshold_drop:.2f}). "
                "High probability of unauthorized harvest, gur halwai diversion, or cane poaching."
            )
            action = "Dispatch field cane inspector immediately to verify standing crop vs unauthorized cutting."
        else:
            event_type = "NORMAL_CANOPY"
            severity = "NOMINAL"
            alert_message = "Canopy integrity intact; no rapid vegetative collapse observed."
            action = "Continue standard rolling satellite monitoring."

        return {
            "anomaly_detected": collapse_detected,
            "event_type": event_type,
            "severity": severity,
            "delta_ndvi": round(delta_ndvi, 4),
            "drop_magnitude": round(drop_magnitude, 4),
            "effective_5d_drop": round(effective_drop, 4),
            "threshold_drop": threshold_drop,
            "days_interval": interval_days,
            "current_ndvi": current_ndvi,
            "previous_ndvi": previous_ndvi,
            "ndre_collapsed": ndre_collapsed,
            "delta_ndre": round(delta_ndre, 4) if previous_ndre is not None else None,
            "alert_message": alert_message,
            "recommended_action": action
        }

    # ------------------------------------------------------------------------
    # Track B Helpers: Inversion, Event Triggers, and Varietal Profiling
    # ------------------------------------------------------------------------
    @classmethod
    def check_inversion_risk(
        cls,
        crop_age_days: float,
        cane_type: str = "SURU",
        purity: Optional[float] = None,
        variety: str = "DEFAULT"
    ) -> Dict[str, Any]:
        """
        Determines post-maturity inversion risk based on crop age and juice purity.
        Inversion triggers when:
        - Adsali: crop_age_days > 480
        - Suru / Khodwa / Other: crop_age_days > 375 (or > 430 for CoM-0265)
        - OR juice purity < 80.0% in mature crop (age >= min maturity age)
        """
        c_type = str(cane_type).strip().upper()
        is_adsali = "ADSALI" in c_type

        v_key = normalize_variety_name(variety)
        v_profile = VARIETAL_PROFILES[v_key]

        if is_adsali:
            age_limit = INVERSION_AGE_DAYS_ADSALI
            min_maturity_age = 365.0
        else:
            # CoM-0265 is a late-maturing variety requiring 13+ months (390+ days)
            # Its plateau is 390-425 days; inversion occurs after ~430 days
            if v_key == 'COM 0265':
                age_limit = 430.0
                min_maturity_age = 360.0
            else:
                age_limit = INVERSION_AGE_DAYS_SURU
                min_maturity_age = 270.0

        age_exceeded = crop_age_days > age_limit
        # Low purity (< 80%) indicates inversion when cane has reached maturity age (or age unknown/zero).
        # Immature young cane naturally has low purity due to reducing sugars before sucrose synthesis.
        purity_low = False
        if purity is not None and purity > 0:
            if (crop_age_days <= 0 or crop_age_days >= min_maturity_age) and purity < INVERSION_PURITY_THRESHOLD:
                purity_low = True

        is_inversion = age_exceeded or purity_low

        reasons = []
        if age_exceeded:
            reasons.append(f"Crop age ({crop_age_days:.0f}d) exceeds maturity ceiling ({age_limit:.0f}d for {c_type})")
        if purity_low:
            reasons.append(f"Juice purity ({purity:.1f}%) dropped below critical threshold ({INVERSION_PURITY_THRESHOLD}%)")

        # Inversion daily Pol loss rate: -0.04 to -0.10 %/day
        pol_loss_daily_rate = 0.0
        if is_inversion:
            # CoM-0265 inverts rapidly once overmature; Co-86032 inverts more slowly
            if v_key == 'COM 0265':
                pol_loss_daily_rate = -0.08  # rapid breakdown
            elif v_key == 'CO 86032':
                pol_loss_daily_rate = -0.05  # moderate breakdown
            else:
                pol_loss_daily_rate = -0.06

            # If purity is severely low, scale towards maximum loss
            if purity is not None and purity < 75.0:
                pol_loss_daily_rate = min(pol_loss_daily_rate, -0.085)
            # Bound within [-0.10, -0.04]
            pol_loss_daily_rate = max(INVERSION_POL_LOSS_MIN_PER_DAY, min(INVERSION_POL_LOSS_MAX_PER_DAY, pol_loss_daily_rate))

        return {
            "is_inversion": is_inversion,
            "age_exceeded": age_exceeded,
            "purity_low": purity_low,
            "age_limit_days": age_limit,
            "crop_age_days": crop_age_days,
            "cane_type": cane_type,
            "variety": v_profile['name'],
            "pol_loss_daily_rate": round(pol_loss_daily_rate, 4),
            "pol_loss_14d": round(pol_loss_daily_rate * 14.0, 3),
            "reasons": reasons
        }

    @classmethod
    def evaluate_chilling_trigger(
        cls,
        tmin: Optional[float],
        tmax: Optional[float] = None,
        diurnal_range: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Evaluates chilling night event:
        Tmin <= 15°C and diurnal temperature range (Tmax - Tmin) >= 14°C.
        Cold night temperature arrests vegetative elongation, activating sucrose synthesis.
        """
        if tmin is None:
            return {"active": False, "reason": "No temperature telemetry"}

        dtr = diurnal_range
        if dtr is None and tmax is not None:
            dtr = tmax - tmin

        if dtr is None:
            return {"active": False, "reason": "Diurnal range unavailable"}

        active = (tmin <= CHILLING_TMIN_MAX) and (dtr >= CHILLING_DTR_MIN)
        return {
            "active": active,
            "tmin": tmin,
            "diurnal_range": dtr,
            "acceleration_factor": 1.15 if active else 1.0,
            "description": (
                "Chilling night conditions met (Tmin <= 15°C, DTR >= 14°C): sucrose synthase activated; "
                "ripening accelerated towards upper bound (+0.055 °Bx/day)."
                if active else "No chilling event detected."
            )
        }

    @classmethod
    def evaluate_drying_off_trigger(
        cls,
        delta_ndwi_15d: Optional[float],
        rainfall_15d_mm: float = 0.0
    ) -> Dict[str, Any]:
        """
        Evaluates pre-harvest drying-off trigger:
        15-day delta NDWI <= -0.08 without rain (<= 5mm).
        Locks in sucrose by suppressing vegetative flushing and boosting juice purity.
        """
        if delta_ndwi_15d is None:
            return {"active": False, "reason": "No NDWI telemetry"}

        active = (delta_ndwi_15d <= DRYING_OFF_NDWI_DROP) and (rainfall_15d_mm <= DRYING_OFF_MAX_RAIN_MM)
        return {
            "active": active,
            "delta_ndwi_15d": delta_ndwi_15d,
            "rainfall_15d_mm": rainfall_15d_mm,
            "purity_boost": 0.5 if active else 0.0,
            "description": (
                "Pre-harvest water withholding active (15d delta NDWI <= -0.08 with zero/trace rain): "
                "vegetative flush halted; sucrose locked in."
                if active else "Standard moisture level."
            )
        }

    @classmethod
    def evaluate_gdd_thermal_gate(
        cls,
        delta_gdd: Optional[float],
        threshold: float = GDD_THERMAL_GATE_MIN
    ) -> Dict[str, Any]:
        """
        Evaluates GDD thermal gate (delta GDD >= 120 °C-days over 14-day window).
        Ensures thermal energy is sufficient for enzymatic sucrose accumulation.
        """
        if delta_gdd is None:
            # Default to passing gate if weather model is absent
            return {
                "gate_passed": True,
                "delta_gdd": 140.0,
                "threshold": threshold,
                "thermal_multiplier": 1.0,
                "is_simulated": True,
                "description": "GDD thermal gate open by default (simulated)."
            }

        gate_passed = delta_gdd >= threshold
        return {
            "gate_passed": gate_passed,
            "delta_gdd": delta_gdd,
            "threshold": threshold,
            "thermal_multiplier": 1.0 if gate_passed else max(0.40, delta_gdd / threshold),
            "description": (
                f"GDD thermal gate open (delta GDD = {delta_gdd:.1f} >= {threshold:.1f} °C-days)."
                if gate_passed else
                f"GDD thermal gate closed (delta GDD = {delta_gdd:.1f} < {threshold:.1f} °C-days): ripening kinetics slowed."
            )
        }

    @classmethod
    def detect_arrowing(
        cls,
        delta_ndre: Optional[float] = None,
        swir_spike: bool = False,
        delta_swir: Optional[float] = None,
        current_ndre: Optional[float] = None,
        previous_ndre: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Arrowing (flowering) detection:
        RedEdge NDRE drop (delta NDRE <= -0.05) with SWIR spike.
        Triggers emergency harvest countdown of 60–75 days before terminal stalk pithiness.
        """
        if delta_ndre is None and current_ndre is not None and previous_ndre is not None:
            delta_ndre = current_ndre - previous_ndre

        has_swir_spike = swir_spike
        if delta_swir is not None and delta_swir >= 0.04:
            has_swir_spike = True

        arrowing_detected = False
        if delta_ndre is not None and delta_ndre <= ARROWING_NDRE_DROP_THRESHOLD and has_swir_spike:
            arrowing_detected = True

        return {
            "arrowing_detected": arrowing_detected,
            "delta_ndre": round(delta_ndre, 4) if delta_ndre is not None else None,
            "swir_spike": has_swir_spike,
            "emergency_harvest_window_days": (EMERGENCY_HARVEST_MIN_DAYS, EMERGENCY_HARVEST_MAX_DAYS) if arrowing_detected else None,
            "emergency_harvest_deadline_days": EMERGENCY_HARVEST_MAX_DAYS if arrowing_detected else None,
            "alert_message": (
                "Arrowing/Flowering detected: Terminal vegetative growth terminated by inflorescence. "
                "Emergency harvest countdown of 60–75 days initiated before severe stalk pithiness and inversion."
                if arrowing_detected else "No arrowing detected."
            )
        }

    # ------------------------------------------------------------------------
    # Track B: 10-14 Day Rolling Ripening Projection Engine
    # ------------------------------------------------------------------------
    @classmethod
    def project_14day_ripening(
        cls,
        current_brix: float,
        current_pol: float,
        crop_age_days: float,
        cane_type: str = "SURU",
        variety: str = "DEFAULT",
        cadence_days: int = 14,
        tmin: Optional[float] = None,
        tmax: Optional[float] = None,
        diurnal_range: Optional[float] = None,
        delta_ndwi_15d: Optional[float] = None,
        rainfall_15d_mm: float = 0.0,
        delta_gdd: Optional[float] = None,
        delta_ndre: Optional[float] = None,
        swir_spike: bool = False,
        delta_swir: Optional[float] = None,
        top_to_bottom_ratio: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Projects Brix, Pol, and CCS on a 14-day rolling window adhering to
        biophysical boundaries and environmental triggers:

        - Active Ripening (months 9–11 Suru/Khodwa, 12–15 Adsali):
          +0.035 to +0.055 °Bx/day (+0.50 to +0.80 °Bx / 14 days, max +1.50 °Bx/month).
        - Peak Maturity Plateau (months 11–12 Suru, 15–17 Adsali):
          net change 0.00 ± 0.02 °Bx/day, Top-to-Bottom Brix ratio 0.95–1.00.
        - Post-Maturity Inversion:
          Pol loss -0.04 to -0.10 %/day.
        """
        cadence_days = int(max(1, min(30, cadence_days)))
        c_type = str(cane_type).strip().upper()
        is_adsali = "ADSALI" in c_type

        v_key = normalize_variety_name(variety)
        v_profile = VARIETAL_PROFILES[v_key]

        initial_purity = calculate_purity(current_pol, current_brix)
        initial_ccs = calculate_ccs(current_pol, current_brix)

        # 1. Evaluate Inversion Status
        inv_eval = cls.check_inversion_risk(
            crop_age_days=crop_age_days,
            cane_type=cane_type,
            purity=initial_purity,
            variety=variety
        )
        is_inversion = inv_eval["is_inversion"]

        # 2. Evaluate Biophysical Triggers
        chilling_eval = cls.evaluate_chilling_trigger(tmin=tmin, tmax=tmax, diurnal_range=diurnal_range)
        drying_eval = cls.evaluate_drying_off_trigger(delta_ndwi_15d=delta_ndwi_15d, rainfall_15d_mm=rainfall_15d_mm)
        gdd_eval = cls.evaluate_gdd_thermal_gate(delta_gdd=delta_gdd)
        arrowing_eval = cls.detect_arrowing(delta_ndre=delta_ndre, swir_spike=swir_spike, delta_swir=delta_swir)

        # 3. Determine Physiological Phase
        # Months / Days thresholds:
        # Suru / Khodwa:
        #   Active Ripening: months 9–11 (270–335 days). CoM-0265: needs 13+ months (390+ days).
        #   Plateau: months 11–12 (335–375 days).
        #   Inversion: > 375 days (or purity < 80%).
        # Adsali:
        #   Active Ripening: months 12–15 (365–455 days).
        #   Plateau: months 15–17 (455–510 days, inversion threshold > 480 days).
        #   Inversion: > 480 days.

        phase: str
        daily_brix_rate: float
        daily_pol_rate: float
        velocity: str
        calc_top_to_bottom: float

        if is_inversion:
            phase = "POST_MATURITY_INVERSION"
            velocity = "INVERSION"
            # Pol loss: -0.04 to -0.10 %/day
            daily_pol_rate = inv_eval["pol_loss_daily_rate"]
            # Brix changes slightly positive or flat due to stalk desiccation
            daily_brix_rate = 0.010  # +0.14 °Bx / 14 days
            calc_top_to_bottom = top_to_bottom_ratio if top_to_bottom_ratio is not None else 0.92

        else:
            # Check for Peak Maturity Plateau
            is_plateau = False
            if is_adsali:
                if 455 <= crop_age_days <= 480:
                    is_plateau = True
            else:
                # Suru / Khodwa
                if v_key == 'COM 0265':
                    # CoM-0265 reaches plateau later (390-420 days)
                    if 390 <= crop_age_days <= 425:
                        is_plateau = True
                else:
                    if 335 <= crop_age_days <= 375:
                        is_plateau = True

            # If top-to-bottom ratio is already in [0.95, 1.00] and CCS is mature, confirm plateau
            if top_to_bottom_ratio is not None and top_to_bottom_ratio >= PLATEAU_TOP_BOTTOM_RATIO_MIN and initial_ccs >= 11.2:
                is_plateau = True

            if is_plateau:
                phase = "PEAK_MATURITY_PLATEAU"
                velocity = "PLATEAU"
                # net change 0.00 ± 0.02 °Bx/day
                daily_brix_rate = 0.005  # slightly positive within [-0.02, 0.02]
                daily_pol_rate = 0.004   # stable plateau
                calc_top_to_bottom = top_to_bottom_ratio if top_to_bottom_ratio is not None else 0.98

            else:
                # Check for Active Ripening vs Vegetative
                is_active = False
                if is_adsali:
                    if 365 <= crop_age_days < 455:
                        is_active = True
                else:
                    if v_key == 'COM 0265':
                        # CoM-0265: needs 13+ months (390+ days), slower early accumulation until 360d
                        if 360 <= crop_age_days < 390:
                            is_active = True
                    else:
                        if 270 <= crop_age_days < 335:
                            is_active = True

                if is_active:
                    phase = "ACTIVE_RIPENING"
                    velocity = "ACCUMULATION"
                    # Baseline rate between 0.035 and 0.055 °Bx/day
                    # For 14 days, baseline = +0.50 to +0.80 °Bx
                    base_rate = 0.043  # ~ +0.60 °Bx / 14 days

                    # Varietal modifier
                    if v_key == 'CO 86032':
                        base_rate *= 1.08  # early accumulator
                    elif v_key == 'COM 0265':
                        if crop_age_days < 390:
                            base_rate *= 0.85  # delayed sugar accumulation

                    # Chilling night trigger pushes towards upper bound
                    if chilling_eval["active"]:
                        base_rate = max(base_rate, 0.052) * chilling_eval["acceleration_factor"]

                    # GDD thermal gate
                    base_rate *= gdd_eval["thermal_multiplier"]

                    # Strictly clamp daily Brix rate to biophysical limits: [+0.035, +0.055]
                    daily_brix_rate = max(ACTIVE_BRIX_MIN_PER_DAY, min(ACTIVE_BRIX_MAX_PER_DAY, base_rate))

                    # Pol accumulation rate: proportional to purity
                    purity_factor = 0.88
                    if drying_eval["active"]:
                        purity_factor += 0.04  # locked-in sucrose boosts purity
                    daily_pol_rate = daily_brix_rate * purity_factor

                    # Top-to-Bottom Brix ratio rises during active ripening (0.75 -> 0.94)
                    calc_top_to_bottom = top_to_bottom_ratio if top_to_bottom_ratio is not None else min(0.94, 0.70 + (crop_age_days / 500.0) * 0.25)

                else:
                    # Vegetative stage (young cane)
                    phase = "VEGETATIVE"
                    velocity = "VEGETATIVE"
                    daily_brix_rate = 0.020
                    daily_pol_rate = 0.015
                    calc_top_to_bottom = top_to_bottom_ratio if top_to_bottom_ratio is not None else 0.65

        # 4. Project Forward by cadence_days with Physiological Ceilings
        delta_brix = daily_brix_rate * cadence_days
        delta_pol = daily_pol_rate * cadence_days

        # Ensure active ripening complies with 14-day boundaries and monthly ceiling
        if phase == "ACTIVE_RIPENING":
            if cadence_days == 14:
                # Strictly bounded to [+0.50, +0.80] °Bx / 14 days
                delta_brix = max(ACTIVE_BRIX_14D_MIN, min(ACTIVE_BRIX_14D_MAX, delta_brix))
            elif cadence_days < 14:
                delta_brix = max(ACTIVE_BRIX_MIN_PER_DAY * cadence_days, min(ACTIVE_BRIX_MAX_PER_DAY * cadence_days, delta_brix))
            else:
                # For longer cadence windows (e.g. 21 to 30 days), enforce maximum +1.50 °Bx/month ceiling
                max_period_brix = (MAX_BRIX_PER_MONTH / 30.0) * cadence_days
                delta_brix = min(delta_brix, max_period_brix)

        projected_brix = round(max(0.0, current_brix + delta_brix), 2)
        projected_pol = round(max(0.0, current_pol + delta_pol), 2)
        projected_purity = calculate_purity(projected_pol, projected_brix)
        projected_ccs = calculate_ccs(projected_pol, projected_brix)

        delta_ccs = round(projected_ccs - initial_ccs, 2)
        delta_purity = round(projected_purity - initial_purity, 2)

        # Build Harvest Advisory
        advisory: str
        if arrowing_eval["arrowing_detected"]:
            advisory = "EMERGENCY_HARVEST_60_75D: Arrowing active; cut parcel before pithiness."
        elif phase == "POST_MATURITY_INVERSION":
            advisory = "IMMEDIATE_CUT_REQUIRED: Cane in post-maturity inversion; crushing order priority HIGH to prevent further Pol loss."
        elif phase == "PEAK_MATURITY_PLATEAU":
            advisory = "OPTIMAL_HARVEST_WINDOW: Parcel at peak maturity plateau; schedule cutting within 10–20 days."
        elif phase == "ACTIVE_RIPENING":
            advisory = "ACTIVE_ACCUMULATION: Sugar accumulating steadily; withhold irrigation 15 days before planned harvest."
        else:
            advisory = "VEGETATIVE_HOLD: Crop immature; continue standard agronomic practices."

        return {
            "crop_age_days": crop_age_days,
            "cane_type": cane_type,
            "variety": v_profile['name'],
            "variety_code": v_key,
            "physiological_phase": phase,
            "velocity": velocity,
            "cadence_days": cadence_days,
            "initial": {
                "brix": current_brix,
                "pol": current_pol,
                "purity": initial_purity,
                "ccs": initial_ccs
            },
            "projected": {
                "brix": projected_brix,
                "pol": projected_pol,
                "purity": projected_purity,
                "ccs": projected_ccs
            },
            "delta_projection": {
                "delta_brix": round(delta_brix, 2),
                "delta_pol": round(delta_pol, 2),
                "delta_purity": delta_purity,
                "delta_ccs": delta_ccs
            },
            "daily_rates": {
                "brix_per_day": round(daily_brix_rate, 4),
                "pol_per_day": round(daily_pol_rate, 4)
            },
            "top_to_bottom_brix_ratio": round(calc_top_to_bottom, 3),
            "biophysical_boundaries": {
                "active_brix_daily_range": [ACTIVE_BRIX_MIN_PER_DAY, ACTIVE_BRIX_MAX_PER_DAY],
                "active_brix_14d_range": [ACTIVE_BRIX_14D_MIN, ACTIVE_BRIX_14D_MAX],
                "max_brix_per_month": MAX_BRIX_PER_MONTH,
                "plateau_brix_daily_range": [PLATEAU_BRIX_DELTA_MIN, PLATEAU_BRIX_DELTA_MAX],
                "plateau_ratio_range": [PLATEAU_TOP_BOTTOM_RATIO_MIN, PLATEAU_TOP_BOTTOM_RATIO_MAX],
                "inversion_pol_loss_daily_range": [INVERSION_POL_LOSS_MIN_PER_DAY, INVERSION_POL_LOSS_MAX_PER_DAY]
            },
            "triggers": {
                "chilling_nights": chilling_eval,
                "drying_off": drying_eval,
                "gdd_gate": gdd_eval,
                "arrowing": arrowing_eval
            },
            "inversion_risk": inv_eval,
            "harvest_advisory": advisory
        }

    # ------------------------------------------------------------------------
    # Dual-Track Orchestrator
    # ------------------------------------------------------------------------
    @classmethod
    def run_dual_track_cadence(
        cls,
        # Track A: 5-Day Anomaly Detection
        current_ndvi: float,
        previous_ndvi: float,
        anomaly_interval_days: float = 5.0,
        current_ndre: Optional[float] = None,
        previous_ndre: Optional[float] = None,
        # Track B: 14-Day Ripening Projection
        current_brix: float = 18.0,
        current_pol: float = 15.0,
        crop_age_days: float = 350.0,
        cane_type: str = "SURU",
        variety: str = "DEFAULT",
        weather_params: Optional[Dict[str, Any]] = None,
        satellite_indices: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Executes unified dual-track monitoring:
        Track A: 5-day canopy collapse & unauthorized diversion check.
        Track B: 14-day rolling ripening projection.
        """
        weather = weather_params or {}
        sat = satellite_indices or {}

        track_a = cls.detect_5day_anomaly(
            current_ndvi=current_ndvi,
            previous_ndvi=previous_ndvi,
            interval_days=anomaly_interval_days,
            current_ndre=current_ndre,
            previous_ndre=previous_ndre
        )

        track_b = cls.project_14day_ripening(
            current_brix=current_brix,
            current_pol=current_pol,
            crop_age_days=crop_age_days,
            cane_type=cane_type,
            variety=variety,
            cadence_days=14,
            tmin=weather.get('tmin'),
            tmax=weather.get('tmax'),
            diurnal_range=weather.get('diurnal_range'),
            delta_ndwi_15d=sat.get('delta_ndwi_15d'),
            rainfall_15d_mm=weather.get('rainfall_15d_mm', 0.0),
            delta_gdd=weather.get('delta_gdd'),
            delta_ndre=sat.get('delta_ndre'),
            swir_spike=sat.get('swir_spike', False),
            delta_swir=sat.get('delta_swir'),
            top_to_bottom_ratio=sat.get('top_to_bottom_ratio')
        )

        return {
            "status": "SUCCESS",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "track_a_5day_anomaly": track_a,
            "track_b_14day_ripening": track_b
        }


# ============================================================================
# MODULE LEVEL CONVENIENCE EXPORTS
# ============================================================================

detect_5day_anomaly = BiophysicalRipeningCadenceEngine.detect_5day_anomaly
check_inversion_risk = BiophysicalRipeningCadenceEngine.check_inversion_risk
evaluate_chilling_trigger = BiophysicalRipeningCadenceEngine.evaluate_chilling_trigger
evaluate_drying_off_trigger = BiophysicalRipeningCadenceEngine.evaluate_drying_off_trigger
evaluate_gdd_thermal_gate = BiophysicalRipeningCadenceEngine.evaluate_gdd_thermal_gate
detect_arrowing = BiophysicalRipeningCadenceEngine.detect_arrowing
project_14day_ripening = BiophysicalRipeningCadenceEngine.project_14day_ripening
run_dual_track_cadence = BiophysicalRipeningCadenceEngine.run_dual_track_cadence
