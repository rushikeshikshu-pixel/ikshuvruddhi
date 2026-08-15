"""
IkshuVruddhi FastAPI Satellite Engine Backend
Exposes live Sentinel-2 L2A raster sampling, SCL cloud-masking, and morphological snapping to the dashboard.
"""

import os
import json
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

from ml.copernicus_client import CopernicusCDSEProcessEngine
from ml.satellite_engine import polygonize_cane_mask

app = FastAPI(title="IkshuVruddhi Real Satellite Ingestion API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = CopernicusCDSEProcessEngine()

class PolygonRequest(BaseModel):
    farm_id: str
    polygon: str # lat,lon#lat,lon#...
    date: Optional[str] = "2026-08-15"
    crop_age_days: Optional[int] = 280

@app.get("/api/health")
def health_check():
    has_credentials = bool(os.getenv("CDSE_CLIENT_ID") and os.getenv("CDSE_CLIENT_SECRET"))
    return {
        "service": "IkshuVruddhi Satellite API",
        "live_cdse_configured": has_credentials,
        "mode": "LIVE_SATELLITE" if has_credentials else "SIMULATION_OFFLINE"
    }

@app.post("/api/satellite/process_plot")
def process_plot_satellite_raster(req: PolygonRequest):
    coords = [list(map(float, p.split(","))) for p in req.polygon.split("#")]
    if len(coords) < 3:
        raise HTTPException(status_code=400, detail="Polygon must contain at least 3 coordinates.")

    # 1. Fetch authentic Sentinel-2 L2A raster
    raster_result = engine.fetch_real_sentinel2_l2a_raster(coords, req.date)

    # 2. If unauthenticated / offline, return honest transparent payload
    if not raster_result.get("live_satellite", False):
        return {
            "live_satellite": False,
            "status": "SIMULATION_MODE_OFFLINE",
            "message": "CDSE credentials not active. Displaying physics simulation mode with explicit indicator.",
            "farm_id": req.farm_id
        }

    # 3. Polygonize genuine standing cane mask
    cells = raster_result.get("cells", [])
    snapped = polygonize_cane_mask(cells, coords)

    return {
        "live_satellite": True,
        "status": "LIVE_COPERNICUS_L2A",
        "farm_id": req.farm_id,
        "source": raster_result["source"],
        "valid_pixels": raster_result["valid_cloud_free_pixels"],
        "cloud_pct": raster_result["cloud_contamination_pct"],
        "snapped_polygon": snapped["snapped_polygon"],
        "detected_cane_acres": snapped["standing_cane_acres"],
        "standing_fraction_pct": snapped["standing_fraction_pct"],
        "confidence_pct": snapped["mean_confidence_pct"],
        "cells": cells
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
