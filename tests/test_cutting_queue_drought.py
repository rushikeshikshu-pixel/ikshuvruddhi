# -*- coding: utf-8 -*-
"""Drought-year cutting queue: relative CCS rank, absolute cutoff, mill distance."""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from ml.harvest_api_helper import (
    calculate_cutting_queue,
    get_plot_digital_health_slip,
    haversine_km,
    resolve_plot_distance,
)

DROUGHT = [
    {"id": "low", "gatNo": "Gat 1", "gatNumber": 1, "ccs": 8.2, "brix": 15.2, "pol": 12.4, "estTons": 20, "lat": 19.45, "lon": 75.40, "isGhost": False},
    {"id": "mid", "gatNo": "Gat 2", "gatNumber": 2, "ccs": 9.4, "brix": 16.1, "pol": 13.5, "estTons": 25, "lat": 19.50, "lon": 75.45, "isGhost": False},
    {"id": "high", "gatNo": "Gat 3", "gatNumber": 3, "ccs": 10.1, "brix": 16.8, "pol": 14.2, "estTons": 30, "lat": 19.55, "lon": 75.50, "isGhost": False},
    {"id": "ghost", "gatNo": "Gat 9", "gatNumber": 9, "ccs": 12.5, "brix": 18.0, "pol": 15.0, "estTons": 40, "lat": 19.36, "lon": 75.30, "isGhost": True},
]


def _use(monkeypatch, plots):
    monkeypatch.setattr("ml.harvest_api_helper.get_calibrated_plots_list", lambda: plots)


def test_haversine_same_point_is_zero():
    assert haversine_km(19.361543, 75.297651, 19.361543, 75.297651) == 0.0


def test_distance_is_null_without_coordinates_or_mill():
    kilometres, _meta = resolve_plot_distance({"ccs": 9.1}, mill=None)
    assert kilometres is None


def test_relative_mode_ranks_drought_cane_riper_first(monkeypatch):
    _use(monkeypatch, DROUGHT)
    result = calculate_cutting_queue(eligibility_mode="relative", ccs_percentile=50, target_mt=1000)
    assert result["status"] == "SUCCESS"
    assert result["queue_summary"]["total_queued_parcels"] > 0
    ccs = [parcel["predicted_ccs_pct"] for parcel in result["parcels"]]
    assert ccs == sorted(ccs, reverse=True)
    assert ccs[0] == 10.1
    assert 8.2 not in ccs
    assert result["filter_applied"]["eligibility_mode"] == "relative"
    assert result["filter_applied"]["eligibility_source_tag"] == "X"
    assert result["filter_applied"]["planning_stamp"] == "PLANNING ONLY — NOT VALID FOR PAYMENT"
    assert all(parcel["distance_km"] is not None for parcel in result["parcels"])
    assert all(parcel["distance_method"] == "haversine" for parcel in result["parcels"])


def test_relative_mode_orders_equal_ccs_by_distance_and_transit_uses_it(monkeypatch):
    plots = [
        {"id": "far", "gatNo": "Gat 10", "ccs": 10.0, "brix": 16.0, "pol": 13.0, "estTons": 20, "lat": 20.6, "lon": 75.30, "isGhost": False},
        {"id": "near", "gatNo": "Gat 11", "ccs": 10.0, "brix": 16.0, "pol": 13.0, "estTons": 20, "lat": 19.37, "lon": 75.30, "isGhost": False},
    ]
    _use(monkeypatch, plots)
    result = calculate_cutting_queue(eligibility_mode="relative", ccs_percentile=0, target_mt=1000)
    ordered = result["parcels"]
    assert [parcel["gat_no"] for parcel in ordered] == ["Gat 11", "Gat 10"]
    assert ordered[0]["distance_km"] < ordered[1]["distance_km"]
    assert ordered[0]["travel"]["estimated_transit_hours"] < ordered[1]["travel"]["estimated_transit_hours"]
    assert ordered[0]["travel"]["estimated_inversion_loss_pol"] < ordered[1]["travel"]["estimated_inversion_loss_pol"]


def test_absolute_mode_respects_configured_threshold(monkeypatch):
    _use(monkeypatch, DROUGHT)
    blocked = calculate_cutting_queue(eligibility_mode="absolute", min_ccs=11.2, target_mt=1000)
    assert blocked["queue_summary"]["total_queued_parcels"] == 0
    assert blocked["filter_applied"]["min_ccs_threshold"] == 11.2
    assert blocked["filter_applied"]["eligibility_mode"] == "absolute"

    opened = calculate_cutting_queue(eligibility_mode="absolute", min_ccs=9.0, target_mt=1000)
    assert [parcel["predicted_ccs_pct"] for parcel in opened["parcels"]] == [10.1, 9.4]
    assert all(parcel["predicted_ccs_pct"] >= 9.0 for parcel in opened["parcels"])


def test_absolute_threshold_comes_from_env_when_argument_omitted(monkeypatch):
    _use(monkeypatch, DROUGHT)
    monkeypatch.setenv("IKSHU_MIN_CCS", "10.0")
    from_env = calculate_cutting_queue(eligibility_mode="absolute", target_mt=1000)
    assert [parcel["predicted_ccs_pct"] for parcel in from_env["parcels"]] == [10.1]

    explicit = calculate_cutting_queue(eligibility_mode="absolute", min_ccs=9.0, target_mt=1000)
    assert [parcel["predicted_ccs_pct"] for parcel in explicit["parcels"]] == [10.1, 9.4]


def test_absolute_delta_only_keeps_plots_that_just_crossed_the_cutoff(monkeypatch):
    plots = [
        {"id": "just", "gatNo": "Gat 4", "ccs": 11.3, "estTons": 20, "lat": 19.40, "lon": 75.30, "brix": 17, "pol": 14, "isGhost": False},
        {"id": "long", "gatNo": "Gat 5", "ccs": 12.4, "estTons": 20, "lat": 19.42, "lon": 75.32, "brix": 18, "pol": 15, "isGhost": False},
    ]
    _use(monkeypatch, plots)
    result = calculate_cutting_queue(eligibility_mode="absolute", min_ccs=11.2, delta_only=True, target_mt=1000)
    assert [parcel["gat_no"] for parcel in result["parcels"]] == ["Gat 4"]


def test_road_distance_is_used_when_a_plot_already_has_it(monkeypatch):
    plots = [{
        "id": "road", "gatNo": "Gat 7", "ccs": 10.0, "brix": 16, "pol": 13, "estTons": 20,
        "lat": 19.37, "lon": 75.30, "roadDistanceKm": 12.5, "isGhost": False,
    }]
    _use(monkeypatch, plots)
    result = calculate_cutting_queue(eligibility_mode="relative", ccs_percentile=0, target_mt=100)
    assert result["parcels"][0]["distance_km"] == 12.5
    assert result["parcels"][0]["distance_method"] == "road"


def test_slip_prints_mode_threshold_and_distance(monkeypatch):
    _use(monkeypatch, DROUGHT)
    slip = get_plot_digital_health_slip("Gat 3", eligibility_mode="relative", ccs_percentile=0)
    text = slip["whatsapp_slip_text"]
    recommendation = slip["harvest_recommendation"]
    assert recommendation["eligibility_mode"] == "relative"
    assert recommendation["verdict"] == "READY_TO_CUT_SEASON_RELATIVE"
    assert recommendation["distance_km"] is not None
    assert "relative" in text
    assert "PLANNING ONLY — NOT VALID FOR PAYMENT" in text
    assert "tag *X*" in text

    below = get_plot_digital_health_slip("1", eligibility_mode="absolute", min_ccs=11.2)
    assert below["harvest_recommendation"]["verdict"] == "MONITOR_15_DAYS"

    ripe = dict(DROUGHT[2], ccs=12.4, gatNo="Gat 30", gatNumber=30, id="ripe")
    _use(monkeypatch, DROUGHT + [ripe])
    peak = get_plot_digital_health_slip("30", eligibility_mode="absolute", min_ccs=11.2)
    assert peak["harvest_recommendation"]["verdict"] == "READY_TO_CUT_PEAK_SUCROSE"
    assert "PEAK SUCROSE" in peak["whatsapp_slip_text"]


def test_sample_register_relative_queue_is_non_empty_and_ordered():
    result = calculate_cutting_queue()
    assert result["status"] == "SUCCESS"
    assert result["filter_applied"]["eligibility_mode"] == "relative"
    parcels = result["parcels"]
    assert len(parcels) > 0
    ccs = [parcel["predicted_ccs_pct"] for parcel in parcels]
    assert ccs == sorted(ccs, reverse=True)
    assert all(parcel["predicted_ccs_pct"] + 1e-6 >= result["filter_applied"]["effective_min_ccs"] for parcel in parcels)
    assert all(parcel["distance_km"] is not None for parcel in parcels)
    assert all(parcel["distance_source_tag"] == "D" for parcel in parcels)

    absolute = calculate_cutting_queue(eligibility_mode="absolute")
    assert absolute["queue_summary"]["total_queued_parcels"] == 0
    assert absolute["filter_applied"]["min_ccs_threshold"] == 11.2
