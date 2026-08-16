"""
tests/test_spatial_context.py
Unit tests for geometry deduplication, concentric ring creation, and spatial discrepancy diagnostics.
"""

import pytest
import numpy as np
from shapely.geometry import Polygon, box
from validation.geometry_dedup import find_duplicate_and_overlapping_polygons
from validation.spatial_context import build_concentric_rings, diagnose_spatial_discrepancy

def test_geometry_deduplication():
    """Verifies that identical and near-identical polygons are grouped into the same physical land unit."""
    poly1 = Polygon([(75.10, 19.30), (75.11, 19.30), (75.11, 19.31), (75.10, 19.31)])
    poly2 = Polygon([(75.10, 19.30), (75.11, 19.30), (75.11, 19.31), (75.10, 19.31)]) # Exact duplicate
    poly3 = Polygon([(75.20, 19.40), (75.21, 19.40), (75.21, 19.41), (75.20, 19.41)]) # Separate plot

    parcels = [
        {"plot_no": "54", "polygon": poly1},
        {"plot_no": "55", "polygon": poly2},
        {"plot_no": "56", "polygon": poly3}
    ]

    res = find_duplicate_and_overlapping_polygons(parcels, iou_exact_threshold=0.98)
    assert res["unique_physical_plots_count"] == 2
    assert res["duplicate_plots_count"] == 1
    assert ["54", "55"] in res["duplicate_groups"]
    assert res["plot_to_group_id"]["54"] == res["plot_to_group_id"]["55"]
    assert res["plot_to_group_id"]["54"] != res["plot_to_group_id"]["56"]

def test_concentric_rings_disjointness_and_geometry():
    """Verifies that concentric rings (25m, 50m, 100m, 250m) are valid and disjoint."""
    poly = Polygon([(75.100, 19.300), (75.101, 19.300), (75.101, 19.301), (75.100, 19.301)])
    rings = build_concentric_rings(poly, [25.0, 50.0, 100.0, 250.0])

    assert "ring_25m" in rings
    assert "ring_50m" in rings
    assert "ring_100m" in rings
    assert "ring_250m" in rings

    for name, r in rings.items():
        assert r.is_valid
        assert not r.is_empty
        # Overlapping interior area with source parcel is zero
        assert r.intersection(poly).area < 1e-10

    # Overlapping interior area between disjoint rings is zero
    inter_25_50 = rings["ring_25m"].intersection(rings["ring_50m"])
    assert inter_25_50.area < 1e-10
    inter_50_100 = rings["ring_50m"].intersection(rings["ring_100m"])
    assert inter_50_100.area < 1e-10

def test_diagnose_boundary_shift():
    """Low inside parcel, but high canopy immediately outside (25m/50m) diagnosed as BOUNDARY_OR_POLYGON_SHIFT_SUSPECT."""
    inside_occupancy = 5.0 # Low inside
    ring_stats = {
        "ring_25m": {"mean_ndvi": 0.62, "canopy_pct": 78.0},
        "ring_50m": {"mean_ndvi": 0.55, "canopy_pct": 60.0},
        "ring_100m": {"mean_ndvi": 0.45, "canopy_pct": 30.0},
        "ring_250m": {"mean_ndvi": 0.35, "canopy_pct": 10.0}
    }
    diag = diagnose_spatial_discrepancy(inside_occupancy, ring_stats, nearest_high_canopy_dist_m=35.0)
    assert diag["spatial_discrepancy_stratum"] == "BOUNDARY_OR_POLYGON_SHIFT_SUSPECT"

def test_diagnose_field_specific_harvest_active_cluster():
    """Low inside, low in immediate ring, but high cane parcel exists 118m away (like Plot 21 vs 20)."""
    inside_occupancy = 2.6
    ring_stats = {
        "ring_25m": {"mean_ndvi": 0.30, "canopy_pct": 2.0},
        "ring_50m": {"mean_ndvi": 0.32, "canopy_pct": 5.0},
        "ring_100m": {"mean_ndvi": 0.38, "canopy_pct": 18.0},
        "ring_250m": {"mean_ndvi": 0.42, "canopy_pct": 35.0}
    }
    # Plot 20 is 118m away
    diag = diagnose_spatial_discrepancy(inside_occupancy, ring_stats, nearest_high_canopy_dist_m=118.0)
    assert diag["spatial_discrepancy_stratum"] == "FIELD_SPECIFIC_DISCREPANCY_CLUSTER_ACTIVE"

def test_diagnose_regional_fallow_locality():
    """Low inside and low across entire 100m-250m surroundings diagnosed as REGIONAL_FALLOW_OR_DRY_LOCALITY."""
    inside_occupancy = 0.0
    ring_stats = {
        "ring_25m": {"mean_ndvi": 0.22, "canopy_pct": 0.0},
        "ring_50m": {"mean_ndvi": 0.24, "canopy_pct": 0.0},
        "ring_100m": {"mean_ndvi": 0.25, "canopy_pct": 2.0},
        "ring_250m": {"mean_ndvi": 0.26, "canopy_pct": 5.0}
    }
    diag = diagnose_spatial_discrepancy(inside_occupancy, ring_stats, nearest_high_canopy_dist_m=850.0)
    assert diag["spatial_discrepancy_stratum"] == "REGIONAL_FALLOW_OR_DRY_LOCALITY"

if __name__ == "__main__":
    pytest.main(["-v", __file__])