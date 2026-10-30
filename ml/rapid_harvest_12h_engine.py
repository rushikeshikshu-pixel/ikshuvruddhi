# -*- coding: utf-8 -*-
"""
ml/rapid_harvest_12h_engine.py
==============================
12-to-24-Hour Free Multi-Satellite Rapid Harvest Detection & Mass Balance Engine.

Combines 100% Free Public Government Constellations:
  1. Copernicus Sentinel-1 SAR (C-Band Dual-Pol, 6 AM & 6 PM Day/Night Radar passes)
     - Detects structural canopy & stalk volume collapse (Delta sigma_VH/VV <= -3.5 dB).
     - 100% cloud-proof, fog-proof, and smoke-proof.
  2. NASA / NOAA VIIRS (375m I-Bands, 1:30 AM & 1:30 PM passes)
     - Detects thermal surface heating spike (Delta T_surface >= +8.5 C) when insulating
       cane canopy is removed and bare soil/dry stubble is exposed to solar radiation.
  3. Copernicus Sentinel-2A/B/C & NASA Harmonized Landsat-Sentinel (HLS 10m/30m, 10:45 AM passes)
     - High-resolution optical confirmation and sub-pixel polygon boundary snapping.
     - Calculates delivered vs. standing Pol, Brix, CCS, and Recovery.

Outputs per plot:
  - harvest_state: STANDING_UNCUT | PARTIAL_HARVEST_12H_ACTIVE | PARTIAL_HARVEST_24H_CONFIRMED | FULLY_HARVESTED
  - cut_detection_source: S1_SAR_RADAR_DROP | VIIRS_THERMAL_HEATING | S2_OPTICAL_STEP_CLIFF | FUSED_MULTI_SENSOR
  - detection_latency_hours: 12.0 or 24.0
  - harvested_area_ha, remaining_standing_area_ha
  - harvested_cut_tonnage_mt, remaining_standing_tonnage_mt, harvest_progress_pct
  - cut_pol_pct, cut_brix_bx, cut_ccs_pct, cut_recovery_pct
  - standing_pol_pct, standing_brix_bx, standing_ccs_pct, standing_recovery_pct
"""

import math
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd

# Physical Constants
ICUMSA_POL_COEFF = 1.022
ICUMSA_BRIX_COEFF = 0.292
FACTORY_RECOVERY_KF = 0.814 # Standard realization factor for late-October/November Maharashtra crushing

def calculate_ccs_and_recovery(pol: float, brix: float, kf: float = FACTORY_RECOVERY_KF) -> Tuple[float, float]:
    """Computes Australian ICUMSA Primary Juice CCS and Factory Realized Sugar Recovery."""
    ccs = max(0.0, round(ICUMSA_POL_COEFF * pol - ICUMSA_BRIX_COEFF * brix, 2))
    recovery = max(0.0, round(ccs * kf, 2))
    return ccs, recovery

class RapidHarvest12hEngine:
    """
    Sub-Parcel Multi-Sensor 12h-24h Partial Harvest Detection & Accounting Engine.
    Operates without paid satellite subscriptions.
    """

    def __init__(
        self,
        sar_drop_threshold_db: float = -3.5,
        optical_ndvi_drop_threshold: float = -0.30,
        thermal_spike_threshold_celsius: float = 8.5
    ):
        self.sar_drop_thresh = sar_drop_threshold_db
        self.ndvi_drop_thresh = optical_ndvi_drop_threshold
        self.thermal_spike_thresh = thermal_spike_threshold_celsius

    def evaluate_12h_sar_signal(
        self,
        current_sar_cross_ratio_db: float,
        baseline_sar_cross_ratio_db: float
    ) -> Tuple[bool, float]:
        """
        Evaluates 6 AM / 6 PM Sentinel-1 C-Band SAR depolarization change.
        A steep step-drop indicates loss of vertical stalk volume and canopy scattering.
        """
        delta_sar = current_sar_cross_ratio_db - baseline_sar_cross_ratio_db
        is_cut = bool(delta_sar <= self.sar_drop_thresh)
        return is_cut, round(delta_sar, 2)

    def evaluate_12h_thermal_spike(
        self,
        current_surface_temp_celsius: float,
        canopy_baseline_temp_celsius: float
    ) -> Tuple[bool, float]:
        """
        Evaluates 1:30 PM / 1:30 AM NASA VIIRS 375m thermal response.
        Freshly exposed soil & stubble heats up rapidly compared to standing cool canopies.
        """
        delta_temp = current_surface_temp_celsius - canopy_baseline_temp_celsius
        is_spike = bool(delta_temp >= self.thermal_spike_thresh)
        return is_spike, round(delta_temp, 1)

    def evaluate_24h_optical_confirmation(
        self,
        current_ndvi: float,
        baseline_ndvi: float,
        bare_soil_pct: Optional[float] = None
    ) -> Tuple[bool, float]:
        """
        Evaluates 10:45 AM Sentinel-2 / Landsat-9 optical spectral cliff.
        """
        delta_ndvi = current_ndvi - baseline_ndvi
        is_cut = bool(delta_ndvi <= self.ndvi_drop_thresh or (bare_soil_pct is not None and bare_soil_pct >= 60.0))
        return is_cut, round(delta_ndvi, 3)

    def process_plot_harvest_state(
        self,
        plot_id: str,
        total_registered_area_ha: float,
        baseline_yield_mt_ha: float,
        baseline_pol: float,
        baseline_brix: float,
        subpixel_cut_fraction: float = 0.0,
        current_sar_db: Optional[float] = None,
        baseline_sar_db: Optional[float] = None,
        current_temp_c: Optional[float] = None,
        baseline_temp_c: Optional[float] = None,
        current_ndvi: Optional[float] = None,
        baseline_ndvi: Optional[float] = None,
        mill_weighbridge_tonnes_logged: Optional[float] = None,
        observation_timestamp: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Fuses multi-sensor observations to determine exact 12h-24h harvest progress,
        mass balance, and quality parameters.
        """
        if observation_timestamp is None:
            observation_timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        sar_detected = False
        delta_sar = 0.0
        if current_sar_db is not None and baseline_sar_db is not None:
            sar_detected, delta_sar = self.evaluate_12h_sar_signal(current_sar_db, baseline_sar_db)

        thermal_detected = False
        delta_temp = 0.0
        if current_temp_c is not None and baseline_temp_c is not None:
            thermal_detected, delta_temp = self.evaluate_12h_thermal_spike(current_temp_c, baseline_temp_c)

        optical_detected = False
        delta_ndvi = 0.0
        if current_ndvi is not None and baseline_ndvi is not None:
            optical_detected, delta_ndvi = self.evaluate_24h_optical_confirmation(current_ndvi, baseline_ndvi)

        # Weighbridge direct confirmation
        has_gate_ticket = mill_weighbridge_tonnes_logged is not None and mill_weighbridge_tonnes_logged > 2.0

        # Determine effective cut fraction
        total_biomass_mt = round(total_registered_area_ha * baseline_yield_mt_ha, 1)

        cut_frac = float(np.clip(subpixel_cut_fraction, 0.0, 1.0))
        if has_gate_ticket and cut_frac < 0.05 and total_biomass_mt > 0:
            # Calibrate cut fraction from verified gate weight
            cut_frac = float(np.clip(mill_weighbridge_tonnes_logged / total_biomass_mt, 0.0, 1.0))

        # Classify Harvest State & Primary Detection Source
        if cut_frac <= 0.03 and not sar_detected and not thermal_detected and not optical_detected:
            state = "STANDING_UNCUT"
            det_source = "MULTI_SENSOR_BASELINE"
            latency_h = 24.0
        elif cut_frac >= 0.95:
            state = "FULLY_HARVESTED"
            det_source = "S2_OPTICAL_STEP_CLIFF" if optical_detected else ("S1_SAR_RADAR_DROP" if sar_detected else "WEIGHBRIDGE_FINAL_SLIP")
            latency_h = 24.0 if optical_detected else 12.0
        elif sar_detected or thermal_detected:
            state = "PARTIAL_HARVEST_12H_ACTIVE"
            det_source = "FUSED_12H_RADAR_THERMAL" if (sar_detected and thermal_detected) else ("S1_SAR_RADAR_DROP" if sar_detected else "VIIRS_THERMAL_HEATING")
            latency_h = 12.0
            if cut_frac < 0.10:
                cut_frac = 0.25 # Typical first-day toli cut if sub-pixel boundary pending
        elif optical_detected or has_gate_ticket:
            state = "PARTIAL_HARVEST_24H_CONFIRMED"
            det_source = "S2_OPTICAL_STEP_CLIFF" if optical_detected else "WEIGHBRIDGE_TRIGGERED_CONFIRMATION"
            latency_h = 24.0
        else:
            state = "PARTIAL_HARVEST_12H_ACTIVE" if cut_frac > 0 else "STANDING_UNCUT"
            det_source = "SUBPIXEL_CANOPY_ANALYSIS"
            latency_h = 12.0

        # Calculate Harvested vs. Standing Mass Balance
        cut_area = round(total_registered_area_ha * cut_frac, 2)
        standing_area = max(0.0, round(total_registered_area_ha - cut_area, 2))

        cut_tonnage = round(cut_area * baseline_yield_mt_ha, 1)
        if has_gate_ticket:
            cut_tonnage = round(float(mill_weighbridge_tonnes_logged), 1)

        standing_tonnage = max(0.0, round(total_biomass_mt - cut_tonnage, 1))
        harvest_progress_pct = round((cut_tonnage / max(1.0, total_biomass_mt)) * 100.0, 1)

        # Quality Accounting: Cut Portion vs Remaining Standing Portion
        # Cut portion was harvested immediately
        cut_pol = round(baseline_pol, 2)
        cut_brix = round(baseline_brix, 2)
        cut_ccs, cut_rec = calculate_ccs_and_recovery(cut_pol, cut_brix)

        # Standing portion continues ripening if harvest took 12-24h
        standing_pol = round(baseline_pol + (0.15 if standing_area > 0.5 else 0.0), 2)
        standing_brix = round(baseline_brix + (0.18 if standing_area > 0.5 else 0.0), 2)
        standing_ccs, standing_rec = calculate_ccs_and_recovery(standing_pol, standing_brix)

        return {
            "plot_id": str(plot_id),
            "harvest_state": state,
            "cut_detection_source": det_source,
            "detection_latency_hours": latency_h,
            "observation_timestamp": observation_timestamp,
            "harvest_progress_pct": harvest_progress_pct,
            "total_registered_area_ha": total_registered_area_ha,
            "harvested_area_ha": cut_area,
            "remaining_standing_area_ha": standing_area,
            "total_biomass_tonnage_mt": total_biomass_mt,
            "harvested_cut_tonnage_mt": cut_tonnage,
            "remaining_standing_tonnage_mt": standing_tonnage,
            "cut_pol_pct": cut_pol,
            "cut_brix_bx": cut_brix,
            "cut_ccs_pct": cut_ccs,
            "cut_recovery_pct": cut_rec,
            "standing_pol_pct": standing_pol,
            "standing_brix_bx": standing_brix,
            "standing_ccs_pct": standing_ccs,
            "standing_recovery_pct": standing_rec,
            "delta_sar_db": delta_sar,
            "delta_temp_celsius": delta_temp,
            "delta_ndvi": delta_ndvi
        }
