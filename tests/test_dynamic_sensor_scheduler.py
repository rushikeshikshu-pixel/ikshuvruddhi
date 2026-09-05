"""
tests/test_dynamic_sensor_scheduler.py
Unit tests for Inward Parcel Buffering and Economic Sensor Scheduling.
"""

import pytest
from shapely.geometry import Polygon
from ml.dynamic_sensor_scheduler import buffer_parcel_inward, evaluate_sensor_escalation

def test_inward_parcel_buffering():
    # 100m x 100m square in Gangamai area (approx 2.47 acres)
    # 0.001 deg lat ~ 111m, 0.001 deg lon ~ 105m
    coords = [
        (75.3100, 19.3400),
        (75.3110, 19.3400),
        (75.3110, 19.3410),
        (75.3100, 19.3410),
        (75.3100, 19.3400)
    ]

    buffered_poly = buffer_parcel_inward(coords, inward_buffer_meters=6.0)

    assert buffered_poly is not None
    assert not buffered_poly.is_empty
    # Interior area must be smaller than original area (boundary stripped)
    orig_poly = Polygon(coords)
    assert buffered_poly.area < orig_poly.area

def test_inward_buffering_small_parcel_fallback():
    # Very small narrow parcel (~0.1 acre)
    small_coords = [
        (75.31000, 19.34000),
        (75.31010, 19.34000),
        (75.31010, 19.34010),
        (75.31000, 19.34010),
        (75.31000, 19.34000)
    ]
    buffered_poly = buffer_parcel_inward(small_coords, inward_buffer_meters=8.0)
    assert buffered_poly is not None
    assert not buffered_poly.is_empty

def test_sensor_escalation_normal_condition():
    # 1.0 acre, clear weather, low cloud gap (2 days), high confidence
    res = evaluate_sensor_escalation(
        parcel_acres=1.0,
        expected_yield_t_ha=85.0,
        cloud_gap_days=2,
        is_in_harvest_window=False,
        current_model_confidence=0.92,
        planet_pass_cost_inr=1200.0
    )
    assert res["escalate_to_planet"] is False
    assert res["recommended_tier"] == "TIER_1_SENTINEL_LISS_BACKBONE"
    assert res["net_information_value_inr"] < 0

def test_sensor_escalation_high_risk_condition():
    # 4.0 acre high-value seed cane block, 16-day cloud gap during active harvest window, low confidence (0.50)
    res = evaluate_sensor_escalation(
        parcel_acres=4.0,
        expected_yield_t_ha=110.0,
        sugar_cane_frp_per_tonne=3400.0,
        cloud_gap_days=16,
        is_in_harvest_window=True,
        current_model_confidence=0.50,
        planet_pass_cost_inr=1200.0
    )
    # Expected value at risk is thousands of rupees, far exceeding Rs. 1,200 imagery cost
    assert res["escalate_to_planet"] is True
    assert res["recommended_tier"] == "TIER_3_PREMIUM_PLANETSCOPE_ESCALATION"
    assert res["net_information_value_inr"] > 0
    assert "Expected risk reduction" in res["rationale"]