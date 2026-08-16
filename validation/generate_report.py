import os
import pandas as pd

repo_root = r"c:\Users\rishi\.gemini\antigravity\SatCane-AI-Engine"
csv_path = os.path.join(repo_root, "data", "output", "spatio_temporal_audit_320plots.csv")
out_path = r"C:\Users\rishi\.gemini\antigravity\brain\b0072931-e7ba-4c80-a14c-96011ac8c206\full_detailed_audit_report_320_plots.md"

df = pd.read_csv(csv_path)

lines = []
lines.append("# 📊 IKSHU-VRUDDHI: Comprehensive Audit Report (320 Registered Parcels)\n")
lines.append("**Crop & Season**: Adsali Sugarcane Season 2026–2027 (हंगाम २०२६-२७)  ")
lines.append("**Target Catchment**: Gangamai Sugar Mill (Shevgaon / Newasa / Pathardi / Ahilyanagar)  ")
lines.append("**Sensor Engine**: ESA Sentinel-2 L2A Multi-Spectral Cloud-Optimized GeoTIFFs (10m Resolution)  ")
lines.append("**Temporal Windows Analyzed**: Kharif 2025 → Post-Monsoon 2025 → January 2026 → Summer 2026 → August 2026  \n")
lines.append("---\n")

lines.append("## 1. Executive Summary & Macro Distributions\n")
lines.append("Across all **320 registered mill parcel records** (encompassing **318 unique physical cadastral land units**), every parcel was evaluated across **5 decoupled dimensions**:\n")
lines.append("1. **Current Vegetative State (August 2026)**: Evaluates active monsoon canopy status.\n")
lines.append("2. **Event History (Canopy Clearing / Harvest Collapse)**: Identifies step-function clearing events ($10–95$ days, $\\Delta NDVI \\le -0.30$, $\\Delta Canopy \\ge -35\\text{ pp}$).\n")
lines.append("3. **Spatial Cadastral Ring Context (25m / 50m)**: Distinguishes GPS polygon shifts from contiguous healthy blocks and regional fallows.\n")
lines.append("4. **Phenological Duration Profile**: Distinguishes perennial multi-season sugarcane from short-duration rotation crops.\n")
lines.append("5. **Operational Mill Action**: Prescribes the exact field or factory action required.\n\n")

lines.append("### Diagnostic Strata Summary Table\n")
lines.append("| Spatio-Temporal Category | Record Count | % of Records | Unique Land Units | Prescribed Operational Mill Action |")
lines.append("| :--- | :---: | :---: | :---: | :--- |")
for status, grp in df.groupby("spatio_temporal_status"):
    u_cnt = grp["geometry_group_id"].nunique()
    pct = len(grp) / len(df) * 100.0
    action = grp["operational_mill_action"].iloc[0] if pd.notna(grp["operational_mill_action"].iloc[0]) else "Field Verification"
    lines.append(f"| **`{status}`** | **{len(grp)}** | **{pct:.1f}%** | **{u_cnt}** | {action} |")

lines.append("\n---\n")
lines.append("## 2. Village-Wise Parcel Distribution (Top 12 Catchment Villages)\n")
lines.append("| Village Name | Total Registered Parcels | Boundary / GPS Shifts | Active Cane Clusters | Isolated / Low Canopy |")
lines.append("| :--- | :---: | :---: | :---: | :---: |")
v_counts = df["village"].value_counts()
for v, tot in v_counts.head(12).items():
    v_df = df[df["village"] == v]
    b_cnt = len(v_df[v_df["spatial_neighborhood_flag"] == "BOUNDARY_OR_REGISTRATION_DISCREPANCY"])
    a_cnt = len(v_df[v_df["spatial_neighborhood_flag"] == "FIELD_SPECIFIC_DISCREPANCY_ACTIVE_CLUSTER"])
    u_cnt = len(v_df[v_df["spatial_neighborhood_flag"] == "ISOLATED_PARCEL"])
    lines.append(f"| **{v}** | {tot} | {b_cnt} | {a_cnt} | {u_cnt} |")

lines.append("\n---\n")
lines.append("## 3. Dedicated Analysis of Low-Canopy & Clearing Events (54 Records / 53 Units)\n")
lines.append("In the January 23, 2026 satellite snapshot, 54 records showed low canopy. Their multi-temporal and spatial resolution reveals:\n")
lines.append("- **23 Unique Units (24 Records)** showed a **strong canopy-clearing event** between November 2025 and January 2026. This indicates a previous crop was harvested/cleared before the current 2026–27 Adsali cane established.\n")
lines.append("- **6 Units (6 Records)** have **GPS polygon shift discrepancies** where high-canopy cane grows directly adjacent to the registered boundary.\n")
lines.append("- **4 Units (4 Records)** sit directly within active high-canopy clusters within 150m.\n")
lines.append("- **11 Units (11 Records)** exhibit short-duration green profiles characteristic of non-cane Kharif crops.\n")
lines.append("- **3 Units (3 Records)** had no strong green canopy across any sampled date (unplanted registrations).\n")
lines.append("- Only **6 Units (6 Records)** remain truly isolated low-canopy cases requiring ground inspection.\n\n")

lines.append("---\n")
lines.append("## 4. Complete Master Table: All 320 Registered Parcels\n")
lines.append("| Plot No | Farmer Name | Village | Nov 25 NDVI | Jan 26 NDVI | May 26 NDVI | Max NDVI | Spatial Neighborhood Flag | Spatio-Temporal Status | Operational Mill Action |")
lines.append("| :---: | :--- | :--- | :---: | :---: | :---: | :---: | :--- | :--- | :--- |")

for _, r in df.iterrows():
    pno = r["plot_no"]
    farmer = str(r["farmer_name"])[:20]
    vil = str(r["village"])[:16]
    nov_n = f"{r['measured_nov25_ndvi']:.2f}" if pd.notna(r["measured_nov25_ndvi"]) else "-"
    jan_n = f"{r['measured_jan26_ndvi']:.2f}" if pd.notna(r["measured_jan26_ndvi"]) else "-"
    may_n = f"{r['measured_may26_ndvi']:.2f}" if pd.notna(r["measured_may26_ndvi"]) else "-"
    max_n = f"{r['measured_max_annual_ndvi']:.2f}" if pd.notna(r["measured_max_annual_ndvi"]) else "-"
    sp_flag = r["spatial_neighborhood_flag"]
    status = r["spatio_temporal_status"]
    action = str(r["operational_mill_action"])[:30]
    lines.append(f"| **{pno}** | {farmer} | {vil} | {nov_n} | {jan_n} | {may_n} | {max_n} | `{sp_flag}` | `{status}` | {action} |")

lines.append("\n---\n")
lines.append("## 5. Factory & Field Recommendations for Crushing Season 2026–27\n")
lines.append("1. **Cutting Schedule Planning**: Parcels with perennial trajectories ($NDVI \\ge 0.70$ across seasons) should be prioritized for early crushing (October–December 2026).\n")
lines.append("2. **Late-Planted Fields (23 Clearing Units)**: Fields that cleared previous crops in Dec 2025/Jan 2026 should be scheduled for mid-to-late season harvesting (January–March 2027) to allow maximum sugar accumulation (Brix $\\ge 20$).\n")
lines.append("3. **GPS Boundary Correction App**: Mobile survey officers should re-map the 6 boundary-shift plots to align digital cadastral boundaries with actual field coordinates.\n")

with open(out_path, "w", encoding="utf-8") as f:
    f.write("\n".join(lines))

print("Master 320-plot report written successfully.")