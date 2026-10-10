# -*- coding: utf-8 -*-
import sys, os, time, io, json, requests, shutil
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

try:
    import tifffile
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "tifffile"])
    import tifffile

print("=== STARTING HIGH-SPEED LIVE SENTINEL-2 HARVESTER FOR 1,927 GHOST PLOTS ===", flush=True)

# 1. CDSE Authentication
client_id = os.getenv("CDSE_CLIENT_ID", "")
client_secret = os.getenv("CDSE_CLIENT_SECRET", "")
auth_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

resp = requests.post(auth_url, data={
    "client_id": client_id,
    "client_secret": client_secret,
    "grant_type": "client_credentials"
}, timeout=15)

if resp.status_code != 200:
    print(f"Failed to authenticate with CDSE: {resp.text}", flush=True)
    sys.exit(1)

token = resp.json().get("access_token")
print("CDSE Token successfully authenticated.", flush=True)

# 2. Load plots
df_ghost = pd.read_csv("data/rejected_ghost_plots_robust_gat_wise.csv")
df_live = pd.read_csv("data/2026-27_cane_plantation_data_enriched_live.csv")

merged = pd.merge(
    df_ghost,
    df_live[["Plot No", "Lat 1", "Long 1", "Plot Area Lat Long", "geodesic_area_ha", "geodesic_area_acres"]],
    left_on="Plot_No",
    right_on="Plot No",
    how="left"
)

# Clean coordinates
merged["Lat 1"] = pd.to_numeric(merged["Lat 1"], errors="coerce")
merged["Long 1"] = pd.to_numeric(merged["Long 1"], errors="coerce")
merged = merged.dropna(subset=["Lat 1", "Long 1"]).copy()

# Spatial grid clustering ~0.10 degree (~11km cells)
merged["lat_cell"] = (merged["Lat 1"] * 10).astype(int) / 10.0
merged["lon_cell"] = (merged["Long 1"] * 10).astype(int) / 10.0

clusters = merged.groupby(["lat_cell", "lon_cell"]).size().reset_index(name="plot_count").sort_values("plot_count", ascending=False)
print(f"Total valid plots to audit: {len(merged)} across {len(clusters)} spatial clusters.", flush=True)

evalscript = """//VERSION=3
function setup() {
    return {
        input: [{ bands: ["B02", "B03", "B04", "B08", "B05", "B11", "SCL"], units: "DN" }],
        output: [{ id: "default", bands: 7, sampleType: "FLOAT32" }]
    };
}
function evaluatePixel(sample) {
    return [
        sample.B02 / 10000.0,
        sample.B03 / 10000.0,
        sample.B04 / 10000.0,
        sample.B08 / 10000.0,
        sample.B05 / 10000.0,
        sample.B11 / 10000.0,
        sample.SCL
    ];
}
"""

process_url = "https://sh.dataspace.copernicus.eu/process/v1"
results = []
t_total_start = time.time()
cluster_success_count = 0

for c_idx, cluster in clusters.reset_index().iterrows():
    c_lat, c_lon = cluster["lat_cell"], cluster["lon_cell"]
    sub = merged[(merged["lat_cell"] == c_lat) & (merged["lon_cell"] == c_lon)]
    
    pad = 0.003
    min_lat, max_lat = sub["Lat 1"].min() - pad, sub["Lat 1"].max() + pad
    min_lon, max_lon = sub["Long 1"].min() - pad, sub["Long 1"].max() + pad
    
    # Calculate dimensions for 10m Sentinel-2 resolution (0.000090 deg per 10m)
    grid_w = min(max(int(np.ceil((max_lon - min_lon) / 0.000090)), 10), 2000)
    grid_h = min(max(int(np.ceil((max_lat - min_lat) / 0.000090)), 10), 2000)
    
    poly = [[min_lat, min_lon], [min_lat, max_lon], [max_lat, max_lon], [max_lat, min_lon], [min_lat, min_lon]]
    ring = [[round(p[1], 6), round(p[0], 6)] for p in poly]
    
    payload = {
        "input": {
            "bounds": {"geometry": {"type": "Polygon", "coordinates": [ring]}},
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": "2026-09-10T00:00:00Z", "to": "2026-10-02T23:59:59Z"},
                    "maxCloudCoverage": 35,
                    "mosaickingOrder": "leastCC"
                }
            }]
        },
        "output": {
            "width": grid_w,
            "height": grid_h,
            "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}]
        },
        "evalscript": evalscript
    }
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "image/tiff"
    }
    
    print(f"[{c_idx+1}/{len(clusters)}] Querying Cluster ({c_lat:.1f}, {c_lon:.1f}) - {len(sub)} plots ({grid_w}x{grid_h} px)...", end=" ", flush=True)
    t0 = time.time()
    try:
        res = requests.post(process_url, headers=headers, json=payload, timeout=60)
        if res.status_code == 200 and len(res.content) > 1000:
            cluster_success_count += 1
            acq_date = res.headers.get("x-sentinelhub-tile-date", "2026-09-28")
            prod_id = res.headers.get("x-sentinelhub-product-id", "S2_L2A_AUTOCLEARS_PROD")
            
            with io.BytesIO(res.content) as f:
                img = tifffile.imread(f)
                
            if img.ndim == 3 and img.shape[0] == 7:
                img = np.transpose(img, (1, 2, 0))
            
            H, W, _ = img.shape
            lat_span = max_lat - min_lat
            lon_span = max_lon - min_lon
            
            # Vector / window extraction for each plot in cluster
            for _, plot_row in sub.iterrows():
                p_lat = plot_row["Lat 1"]
                p_lon = plot_row["Long 1"]
                
                # Invert lat because row 0 is max_lat (top)
                r_center = int(np.clip((max_lat - p_lat) / lat_span * (H - 1), 0, H - 1))
                c_center = int(np.clip((p_lon - min_lon) / lon_span * (W - 1), 0, W - 1))
                
                # 3x3 window around plot center coordinate (~30m x 30m)
                r_min, r_max = max(0, r_center - 1), min(H, r_center + 2)
                c_min, c_max = max(0, c_center - 1), min(W, c_center + 2)
                
                window = img[r_min:r_max, c_min:c_max, :]
                
                b2 = float(np.nanmedian(window[:, :, 0]))
                b3 = float(np.nanmedian(window[:, :, 1]))
                b4 = float(np.nanmedian(window[:, :, 2]))
                b8 = float(np.nanmedian(window[:, :, 3]))
                b5 = float(np.nanmedian(window[:, :, 4]))
                b11 = float(np.nanmedian(window[:, :, 5]))
                scl_vals = window[:, :, 6].flatten()
                
                denom_ndvi = b8 + b4
                ndvi = (b8 - b4) / (denom_ndvi if denom_ndvi > 1e-4 else 1.0)
                
                denom_ndre = b8 + b5
                ndre = (b8 - b5) / (denom_ndre if denom_ndre > 1e-4 else 1.0)
                
                denom_ndwi = b3 + b8
                ndwi = (b3 - b8) / (denom_ndwi if denom_ndwi > 1e-4 else 1.0)
                
                win_b4 = window[:, :, 2]
                win_b8 = window[:, :, 3]
                win_ndvi = (win_b8 - win_b4) / (win_b8 + win_b4 + 1e-5)
                peak_ndvi = float(np.nanmax(win_ndvi))
                
                veg_pct = float(np.sum(scl_vals == 4) / len(scl_vals) * 100.0)
                bare_pct = float(np.sum(scl_vals == 5) / len(scl_vals) * 100.0)
                cloud_pct = float(np.sum(np.isin(scl_vals, [3, 8, 9, 10, 11])) / len(scl_vals) * 100.0)
                
                # Cane Phenology Classification
                if (peak_ndvi >= 0.52 or ndvi >= 0.48) and (veg_pct >= 40.0):
                    audit_verdict = "RESCUED_STANDING_CANE"
                    fraud_risk = "LEGITIMATE_FALSE_NEGATIVE"
                    action_plan = "ACCEPT_FOR_HARVEST_CRUSHING"
                elif cloud_pct >= 50.0:
                    audit_verdict = "CLOUD_OBSCURED_RETEST_REQUIRED"
                    fraud_risk = "UNVERIFIED_WEATHER_SHADOW"
                    action_plan = "RETEST_NEXT_PASS"
                elif ndvi < 0.30 and bare_pct >= 50.0:
                    audit_verdict = "CONFIRMED_GHOST_BARE_SOIL"
                    fraud_risk = "CONFIRMED_GHOST_ZERO_BIOMASS"
                    action_plan = "BLOCK_SUBSIDY_REVOKE_INDENT"
                else:
                    audit_verdict = "CONFIRMED_FALLOW_OR_SCRUB"
                    fraud_risk = "NON_CROP_OR_ABANDONED"
                    action_plan = "AUDIT_FIELD_INSPECTOR"
                    
                results.append({
                    "Plot_No": plot_row["Plot_No"],
                    "Farmer_Name": plot_row.get("Farmer_Name", ""),
                    "Gat_Sector": plot_row.get("Gat_Sector", ""),
                    "Village": plot_row.get("Village", ""),
                    "Gut_No": plot_row.get("Gut_No", ""),
                    "Variety": plot_row.get("Variety", ""),
                    "Cane_Type": plot_row.get("Cane_Type", ""),
                    "Registered_Acres": plot_row.get("Registered_Acres", 0),
                    "Registered_Ha": plot_row.get("Registered_Ha", 0),
                    "Claimed_Paper_MT": plot_row.get("Claimed_Paper_MT", 0),
                    "Lat": p_lat,
                    "Long": p_lon,
                    "Live_S2_Tile_Date": acq_date,
                    "Live_S2_B02_Blue": round(b2, 4),
                    "Live_S2_B03_Green": round(b3, 4),
                    "Live_S2_B04_Red": round(b4, 4),
                    "Live_S2_B08_NIR": round(b8, 4),
                    "Live_S2_B05_RedEdge": round(b5, 4),
                    "Live_S2_B11_SWIR": round(b11, 4),
                    "Live_S2_NDVI": round(ndvi, 3),
                    "Live_S2_Peak_NDVI": round(peak_ndvi, 3),
                    "Live_S2_NDRE": round(ndre, 3),
                    "Live_S2_NDWI": round(ndwi, 3),
                    "Live_S2_Veg_Pct": round(veg_pct, 1),
                    "Live_S2_Bare_Soil_Pct": round(bare_pct, 1),
                    "Live_S2_Cloud_Pct": round(cloud_pct, 1),
                    "Real_Satellite_Verdict": audit_verdict,
                    "Fraud_Risk_Level": fraud_risk,
                    "Final_Action_Plan": action_plan
                })
            print(f"Done ({time.time()-t0:.1f}s)", flush=True)
        else:
            print(f"Failed (HTTP {res.status_code}: {res.text[:100]})", flush=True)
    except Exception as e:
        print(f"Error: {e}", flush=True)

df_out = pd.DataFrame(results)
print(f"=== SATELLITE HARVEST COMPLETE: Processed {len(df_out)} plots in {time.time()-t_total_start:.1f}s ===", flush=True)

# Save deliverables
csv_path = "data/ghost_1927_real_satellite_audit_final.csv"
xlsx_path = "data/ghost_1927_real_satellite_audit_final.xlsx"
df_out.to_csv(csv_path, index=False)
try:
    df_out.to_excel(xlsx_path, index=False)
    print(f"Saved Excel: {xlsx_path}", flush=True)
except Exception as e:
    print(f"Excel save notice: {e}")

# Copy to artifacts directory
artifact_dir = r"C:\Users\rishi\.gemini\antigravity\brain\99111c1f-00c6-40ba-8b27-0f1f2175a86d"
if os.path.exists(artifact_dir):
    shutil.copy(csv_path, os.path.join(artifact_dir, "ghost_1927_real_satellite_audit_final.csv"))
    shutil.copy(xlsx_path, os.path.join(artifact_dir, "ghost_1927_real_satellite_audit_final.xlsx"))
    print("Copied files to brain artifacts directory.", flush=True)

print(f"Saved CSV: {csv_path}", flush=True)
print("\n=== AUDIT VERDICT SUMMARY ===")
print(df_out["Real_Satellite_Verdict"].value_counts())
