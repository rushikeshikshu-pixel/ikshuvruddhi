"""
supabase_client.py
========================================================================================
Dual-Mode Cloud Persistence Client:
1. Live Supabase REST API (when SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are set).
2. Embedded Local Cloud SQLite Store (when running offline or before remote deployment).
========================================================================================
"""
import os
import json
import sqlite3
from typing import Any, Dict, List, Optional
import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


class SupabaseClient:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
        self.local_db_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "data", "cloud_sync.db"
        )
        self._init_local_db()

    @property
    def is_remote(self) -> bool:
        return bool(self.url and self.key and self.url.startswith("http"))

    @property
    def configured(self) -> bool:
        # Configured in either remote cloud mode or high-performance local cloud mode
        return True

    def _init_local_db(self):
        os.makedirs(os.path.dirname(self.local_db_path), exist_ok=True)
        with sqlite3.connect(self.local_db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS plot_predictions (
                    plot_no INTEGER PRIMARY KEY,
                    gat_no TEXT,
                    village TEXT,
                    farmer TEXT,
                    cane_type TEXT,
                    variety_name TEXT,
                    plantation_date TEXT,
                    satellite_status TEXT,
                    satellite_acquisition_date TEXT,
                    satellite_ndvi REAL,
                    satellite_ndre REAL,
                    registered_area_ha REAL,
                    detected_cane_area_ha REAL,
                    predicted_pol REAL,
                    predicted_brix REAL,
                    predicted_ccs REAL,
                    predicted_tonnage_mt REAL,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS lab_samples (
                    plot_no INTEGER PRIMARY KEY,
                    sample_date TEXT,
                    actual_pol REAL,
                    actual_brix REAL,
                    actual_ccs REAL,
                    collector TEXT,
                    notes TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crop_observations (
                    plot_id TEXT NOT NULL,
                    gat_no TEXT,
                    observation_date TEXT NOT NULL,
                    ndvi REAL NOT NULL,
                    ndre REAL,
                    lswi REAL,
                    usability_pct REAL,
                    sar_vh_db REAL,
                    source TEXT NOT NULL DEFAULT 'sentinel-2',
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (plot_id, observation_date)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS crop_screenings (
                    plot_id TEXT PRIMARY KEY,
                    gat_no TEXT,
                    predicted_crop TEXT NOT NULL,
                    heuristic_score_pct REAL,
                    evidence_completeness_pct REAL,
                    reasoning TEXT,
                    phenology_summary TEXT,
                    model_version TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def _request(self, method: str, table: str, **kwargs):
        if not self.is_remote:
            raise RuntimeError("Remote Supabase is not configured; using local store.")
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }
        headers.update(kwargs.pop("headers", {}))
        response = requests.request(
            method, f"{self.url}/rest/v1/{table}", headers=headers, timeout=30, **kwargs
        )
        response.raise_for_status()
        return response.json() if response.content else []

    def upsert_predictions(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.is_remote:
            return self._request(
                "POST", "plot_predictions", params={"on_conflict": "plot_no"},
                headers={"Prefer": "resolution=merge-duplicates,return=representation"}, json=rows
            )
        # Local SQLite execution
        with sqlite3.connect(self.local_db_path) as conn:
            cur = conn.cursor()
            for r in rows:
                cur.execute("""
                    INSERT OR REPLACE INTO plot_predictions (
                        plot_no, gat_no, village, farmer, cane_type, variety_name,
                        plantation_date, satellite_status, satellite_acquisition_date,
                        satellite_ndvi, satellite_ndre, registered_area_ha, detected_cane_area_ha,
                        predicted_pol, predicted_brix, predicted_ccs, predicted_tonnage_mt
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("plot_no"), r.get("gat_no"), r.get("village"), r.get("farmer"),
                    r.get("cane_type"), r.get("variety_name"), r.get("plantation_date"),
                    r.get("satellite_status"), r.get("satellite_acquisition_date"),
                    r.get("satellite_ndvi"), r.get("satellite_ndre"), r.get("registered_area_ha"),
                    r.get("detected_cane_area_ha"), r.get("predicted_pol"), r.get("predicted_brix"),
                    r.get("predicted_ccs"), r.get("predicted_tonnage_mt")
                ))
            conn.commit()
        return rows

    def list_predictions(self, limit: int = 1000, gat_no: Optional[str] = None):
        if self.is_remote:
            params = {"select": "*", "limit": str(min(max(limit, 1), 10000)), "order": "plot_no.asc"}
            if gat_no:
                params["gat_no"] = f"eq.{gat_no}"
            return self._request("GET", "plot_predictions", params=params)
        with sqlite3.connect(self.local_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            if gat_no:
                cur.execute("SELECT * FROM plot_predictions WHERE gat_no = ? ORDER BY plot_no ASC LIMIT ?", (str(gat_no), limit))
            else:
                cur.execute("SELECT * FROM plot_predictions ORDER BY plot_no ASC LIMIT ?", (limit,))
            return [dict(row) for row in cur.fetchall()]

    def upsert_lab_samples(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.is_remote:
            return self._request(
                "POST", "lab_samples", params={"on_conflict": "plot_no"},
                headers={"Prefer": "resolution=merge-duplicates,return=representation"}, json=rows
            )
        with sqlite3.connect(self.local_db_path) as conn:
            cur = conn.cursor()
            for r in rows:
                cur.execute("""
                    INSERT OR REPLACE INTO lab_samples (
                        plot_no, sample_date, actual_pol, actual_brix, actual_ccs, collector, notes
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("plot_no"), r.get("sample_date"), r.get("actual_pol"),
                    r.get("actual_brix"), r.get("actual_ccs"), r.get("collector"), r.get("notes")
                ))
            conn.commit()
        return rows

    def upsert_crop_observations(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.is_remote:
            return self._request(
                "POST", "crop_observations",
                params={"on_conflict": "plot_id,observation_date"},
                headers={"Prefer": "resolution=merge-duplicates,return=representation"},
                json=rows,
            )
        with sqlite3.connect(self.local_db_path) as conn:
            cur = conn.cursor()
            for r in rows:
                cur.execute("""
                    INSERT OR REPLACE INTO crop_observations (
                        plot_id, gat_no, observation_date, ndvi, ndre, lswi, usability_pct, sar_vh_db, source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("plot_id"), r.get("gat_no"), r.get("observation_date"),
                    r.get("ndvi"), r.get("ndre"), r.get("lswi"), r.get("usability_pct"),
                    r.get("sar_vh_db"), r.get("source", "sentinel-2")
                ))
            conn.commit()
        return rows

    def upsert_crop_screenings(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if self.is_remote:
            return self._request(
                "POST", "crop_screenings", params={"on_conflict": "plot_id"},
                headers={"Prefer": "resolution=merge-duplicates,return=representation"},
                json=rows,
            )
        with sqlite3.connect(self.local_db_path) as conn:
            cur = conn.cursor()
            for r in rows:
                reasoning_str = json.dumps(r.get("reasoning", {})) if isinstance(r.get("reasoning"), dict) else str(r.get("reasoning", ""))
                phenology_str = json.dumps(r.get("phenology_summary", {})) if isinstance(r.get("phenology_summary"), dict) else str(r.get("phenology_summary", ""))
                cur.execute("""
                    INSERT OR REPLACE INTO crop_screenings (
                        plot_id, gat_no, predicted_crop, heuristic_score_pct, evidence_completeness_pct,
                        reasoning, phenology_summary, model_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("plot_id"), r.get("gat_no"), r.get("predicted_crop"),
                    r.get("heuristic_score_pct"), r.get("evidence_completeness_pct"),
                    reasoning_str, phenology_str, r.get("model_version")
                ))
            conn.commit()
        return rows


supabase = SupabaseClient()
