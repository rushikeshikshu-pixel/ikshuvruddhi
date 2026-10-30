# -*- coding: utf-8 -*-
"""
tests/test_rapid_harvest_12h_engine.py
======================================
Unit tests for the 12-to-24-Hour Free Multi-Satellite Rapid Harvest Engine.
"""

import sys, os
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import pytest
from ml.rapid_harvest_12h_engine import (
    RapidHarvest12hEngine,
    calculate_ccs_and_recovery
)

def test_ccs_and_recovery_formula():
    pol = 14.0
    brix = 16.2
    ccs, rec = calculate_ccs_and_recovery(pol, brix)
    # 1.022 * 14.0 - 0.292 * 16.2 = 14.308 - 4.7304 = 9.58
    assert ccs == 9.58
    # 9.58 * 0.814 = 7.798 -> 7.80
    assert rec == 7.80

def test_12h_sar_radar_drop_detection():
    engine = RapidHarvest12hEngine(sar_drop_threshold_db=-3.5)
    # Standing cane cross ratio: -7.0 dB; Cut stubble: -11.5 dB -> delta = -4.5 dB
    is_cut, delta = engine.evaluate_12h_sar_signal(
        current_sar_cross_ratio_db=-11.5,
        baseline_sar_cross_ratio_db=-7.0
    )
    assert is_cut is True
    assert delta == -4.5

def test_12h_thermal_surface_heating_detection():
    engine = RapidHarvest12hEngine(thermal_spike_threshold_celsius=8.5)
    # Standing cool canopy: 27.5 C; Fresh cut bare soil: 38.0 C -> delta = +10.5 C
    is_spike, delta = engine.evaluate_12h_thermal_spike(
        current_surface_temp_celsius=38.0,
        canopy_baseline_temp_celsius=27.5
    )
    assert is_spike is True
    assert delta == 10.5

def test_24h_optical_step_cliff_detection():
    engine = RapidHarvest12hEngine(optical_ndvi_drop_threshold=-0.30)
    # Standing cane NDVI: 0.74; Cut cane NDVI: 0.28 -> delta = -0.46
    is_cut, delta = engine.evaluate_24h_optical_confirmation(
        current_ndvi=0.28,
        baseline_ndvi=0.74
    )
    assert is_cut is True
    assert delta == -0.46

def test_partial_harvest_mass_balance_and_quality():
    engine = RapidHarvest12hEngine()
    result = engine.process_plot_harvest_state(
        plot_id="32154",
        total_registered_area_ha=2.0,
        baseline_yield_mt_ha=85.0,
        baseline_pol=13.80,
        baseline_brix=16.00,
        subpixel_cut_fraction=0.35, # 35% cut in last 12-24h
        current_sar_db=-11.2,
        baseline_sar_db=-7.1
    )

    assert result["harvest_state"] == "PARTIAL_HARVEST_12H_ACTIVE"
    assert result["detection_latency_hours"] == 12.0
    assert result["harvest_progress_pct"] == 35.0
    assert result["total_registered_area_ha"] == 2.0
    assert result["harvested_area_ha"] == 0.70
    assert result["remaining_standing_area_ha"] == 1.30
    assert result["total_biomass_tonnage_mt"] == 170.0
    assert result["harvested_cut_tonnage_mt"] == 59.5
    assert result["remaining_standing_tonnage_mt"] == 110.5

    # Check cut vs standing quality
    assert result["cut_pol_pct"] == 13.80
    assert result["cut_brix_bx"] == 16.00
    assert result["cut_ccs_pct"] == 9.43 # 1.022*13.8 - 0.292*16.0 = 14.1036 - 4.672 = 9.43
    assert result["cut_recovery_pct"] == 7.68 # 9.43 * 0.814 = 7.676 -> 7.68

def test_weighbridge_slip_direct_trigger():
    engine = RapidHarvest12hEngine()
    # Trolley of 25.5 MT logged at weighbridge
    result = engine.process_plot_harvest_state(
        plot_id="32155",
        total_registered_area_ha=1.5,
        baseline_yield_mt_ha=90.0,
        baseline_pol=14.20,
        baseline_brix=16.50,
        subpixel_cut_fraction=0.0, # Optical pass not yet arrived
        mill_weighbridge_tonnes_logged=25.5
    )

    assert result["harvest_state"] == "PARTIAL_HARVEST_24H_CONFIRMED"
    assert result["harvested_cut_tonnage_mt"] == 25.5
    assert result["total_biomass_tonnage_mt"] == 135.0 # 1.5 * 90.0
    assert result["remaining_standing_tonnage_mt"] == 109.5
    assert result["harvest_progress_pct"] == 18.9
