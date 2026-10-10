from types import SimpleNamespace

import numpy as np

from ml import sentinel_phenology as phenology


def test_scene_catalog_searches_once_for_plots_in_same_spatial_cell(monkeypatch):
    calls = []

    def fake_search(bbox, start, end, max_cloud):
        calls.append((bbox, start, end, max_cloud))
        return [{"id": "scene-1", "properties": {"datetime": "2026-01-01T00:00:00Z"}}]

    monkeypatch.setattr(phenology, "stac_search", fake_search)
    rows = [
        {"Plot Area Lat Long": "19.401,75.101#19.402,75.101#19.402,75.102"},
        {"Plot Area Lat Long": "19.405,75.108#19.406,75.108#19.406,75.109"},
    ]
    args = SimpleNamespace(season_start="2025-06-01", season_end="2026-09-30", max_cloud=80)

    catalog = phenology._build_scene_catalog(rows, args)

    assert len(calls) == 1
    assert len(catalog) == 1
    assert next(iter(catalog.values()))[0]["id"] == "scene-1"


def test_monthly_crop_screening_cap_keeps_clearer_candidates():
    items = [
        {"id": "cloudy", "properties": {"datetime": "2026-06-01T00:00:00Z", "eo:cloud_cover": 70}},
        {"id": "clear", "properties": {"datetime": "2026-06-11T00:00:00Z", "eo:cloud_cover": 12}},
        {"id": "also-clear", "properties": {"datetime": "2026-06-21T00:00:00Z", "eo:cloud_cover": 22}},
        {"id": "july", "properties": {"datetime": "2026-07-01T00:00:00Z", "eo:cloud_cover": 40}},
    ]

    selected = phenology._limit_scene_candidates_per_month(items, 2)

    assert [item["id"] for item in selected] == ["clear", "also-clear", "july"]
    assert phenology._limit_scene_candidates_per_month(items, 0) is items


def test_read_band_reuses_worker_local_remote_dataset(monkeypatch):
    class Window:
        width = 2
        height = 2

        def round_offsets(self):
            return self

        def round_lengths(self):
            return self

    class Dataset:
        crs = "EPSG:4326"
        transform = object()

        def __init__(self):
            self.closed = False

        def read(self, *args, **kwargs):
            return np.ones((2, 2), dtype=np.uint16)

        def close(self):
            self.closed = True

    dataset = Dataset()
    opened = []
    monkeypatch.setattr(phenology.rasterio, "open", lambda href: (opened.append(href), dataset)[1])
    monkeypatch.setattr(phenology, "transform_bounds", lambda *args, **kwargs: (0, 0, 1, 1))
    monkeypatch.setattr(phenology, "from_bounds", lambda *args, **kwargs: Window())
    phenology._close_cog_caches()

    first, first_src, _ = phenology.read_band("https://example.test/scene.tif", (0, 0, 1, 1))
    second, second_src, _ = phenology.read_band("https://example.test/scene.tif", (0, 0, 1, 1))

    assert opened == ["https://example.test/scene.tif"]
    assert first_src is second_src is dataset
    assert np.array_equal(first, second)
    phenology._close_cog_caches()
    assert dataset.closed
