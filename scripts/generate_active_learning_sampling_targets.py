#!/usr/bin/env python3
"""Active Learning Core-Sampler Weighbridge Target Generator for Gangamai Sugar.

Implements Pillar 5 (Active Learning Closed-Loop):
Selects 25 optimal daily truckloads from Grade A (Gold) plots across the 22 circles,
balancing varietal representation, crop cycle, and information gain to reach the 1,500
gold-standard training samples needed for the biophysical hybrid PINN-GBDT model.

Generates:
1. 60-Day Strategic Core-Sampling Schedule (1,500 plots).
2. Day 1 Immediate Weighbridge Core-Sampling Manifest (25 trucks).
3. Printable/Mobile Weighbridge & Lab Chemist Slip (HTML).
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np

root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))


def generate_sampling_manifests():
    dqi_csv = root_dir / "web" / "downloads" / "command_area_28847_data_quality_index_audit.csv"
    master_csv = root_dir / "web" / "downloads" / "mill_calibrated_28847_plots_master_register.csv"

    if not dqi_csv.exists() or not master_csv.exists():
        print("Required audit or master CSV files missing.")
        return

    print("Loading audited plots and master register...")
    dqi_df = pd.read_csv(dqi_csv, low_memory=False)
    master_df = pd.read_csv(master_csv, low_memory=False)

    # Merge relevant columns
    cols_to_merge = ["Plot No", "Realistic_Harvest_Batch", "Crush_Priority", "Agri_Manager_Directive", "Millable_Tonnage_MT"]
    master_sub = master_df[[c for c in cols_to_merge if c in master_df.columns]].rename(columns={"Plot No": "plot_no"})
    
    df = pd.merge(dqi_df, master_sub, on="plot_no", how="left")
    total_plots = len(df)
    print(f"Total Command Plots: {total_plots:,}")

    # Step 1: Filter ONLY Grade A (Gold Standard) plots eligible for model training
    gold_candidates = df[df["eligible_for_training"] & (df["quality_grade"] == "A")].copy()
    print(f"Grade A Gold Candidates available: {len(gold_candidates):,} ({len(gold_candidates)/total_plots*100:.1f}%)")

    # Step 2: Prioritize early harvest batches (Opening / Nov 1-15 and Nov 16-30)
    batch_map = {
        "BATCH 1": 1.0,
        "BATCH 2": 0.8,
        "BATCH 3": 0.6,
        "BATCH 4": 0.4,
    }
    
    def get_batch_weight(batch_str):
        if not isinstance(batch_str, str):
            return 0.5
        for b_name, weight in batch_map.items():
            if b_name in batch_str.upper():
                return weight
        return 0.5

    gold_candidates["batch_weight"] = gold_candidates["Realistic_Harvest_Batch"].apply(get_batch_weight)

    # Step 3: Compute Information Gain & Uncertainty Score
    # We want to sample across rare varieties, high-tonnage plots, and diverse crop age distributions
    variety_counts = gold_candidates["variety"].value_counts().to_dict()
    village_counts = gold_candidates["village"].value_counts().to_dict()

    # Rarity weight: Less frequent varieties & villages get higher sampling priority for balance
    gold_candidates["variety_rarity_score"] = gold_candidates["variety"].apply(lambda v: 1.0 / np.log1p(variety_counts.get(v, 1) + 2))
    gold_candidates["village_diversity_score"] = gold_candidates["village"].apply(lambda v: 1.0 / np.log1p(village_counts.get(v, 1) + 2))

    # Age ripeness weighting (plots between 330 and 480 days are in peak active sucrose ripening window)
    def age_ripeness_priority(age):
        if pd.isna(age) or age < 180:
            return 0.2
        if 330 <= age <= 480:
            return 1.0
        elif 300 <= age < 330:
            return 0.7
        else:
            return 0.5

    gold_candidates["age_priority"] = gold_candidates["crop_age_days"].apply(age_ripeness_priority)

    # Composite Uncertainty / Information Gain Score
    gold_candidates["sampling_priority_score"] = (
        gold_candidates["batch_weight"] * 0.35 +
        gold_candidates["age_priority"] * 0.30 +
        gold_candidates["variety_rarity_score"] * 0.20 +
        gold_candidates["village_diversity_score"] * 0.15
    )

    # Sort descending by priority score
    ranked_df = gold_candidates.sort_values(by="sampling_priority_score", ascending=False).reset_index(drop=True)

    # Step 4: Allocate 1,500 plots across 60 days (25 samples per day)
    target_count = min(1500, len(ranked_df))
    scheduled_1500 = ranked_df.head(target_count).copy()
    
    scheduled_1500["sampling_day"] = [(i // 25) + 1 for i in range(len(scheduled_1500))]
    scheduled_1500["target_date_offset_days"] = scheduled_1500["sampling_day"] - 1

    # Save 60-day schedule
    out_dir = root_dir / "web" / "downloads"
    schedule_csv = out_dir / "active_learning_daily_core_sampling_schedule.csv"
    
    export_cols = [
        "sampling_day", "plot_no", "farmer", "village", "gut", "variety", "cane_type",
        "registered_acres", "gps_acres", "crop_age_days", "trust_score",
        "Realistic_Harvest_Batch", "sampling_priority_score"
    ]
    scheduled_1500[export_cols].to_csv(schedule_csv, index=False)
    print(f"Saved 60-Day Sampling Schedule (1,500 plots): {schedule_csv.name}")

    # Step 5: Extract Day 1 Immediate Weighbridge Manifest (25 trucks)
    day1_df = scheduled_1500[scheduled_1500["sampling_day"] == 1].copy()
    
    # Add blank operational logging columns for Weighbridge & Lab Chemist
    day1_df["core_sample_id"] = [f"CS-20261101-{i+1:03d}" for i in range(len(day1_df))]
    day1_df["truck_arrival_time"] = ""
    day1_df["core_brix_bx"] = ""
    day1_df["core_pol_pct"] = ""
    day1_df["calculated_purity_pct"] = ""
    day1_df["lab_sugar_recovery_pct"] = ""
    day1_df["cut_to_crush_hours"] = ""
    day1_df["chemist_signature"] = ""

    manifest_cols = [
        "core_sample_id", "plot_no", "farmer", "village", "variety", "cane_type",
        "crop_age_days", "trust_score", "truck_arrival_time", "core_brix_bx",
        "core_pol_pct", "calculated_purity_pct", "lab_sugar_recovery_pct",
        "cut_to_crush_hours", "chemist_signature"
    ]
    
    day1_csv = out_dir / "today_top25_weighbridge_core_sampling_manifest.csv"
    day1_df[manifest_cols].to_csv(day1_csv, index=False)
    print(f"Saved Day 1 Operational Weighbridge Manifest (25 trucks): {day1_csv.name}")

    # Step 6: Generate Printable Mobile & Clipboard HTML for Weighbridge In-Charge
    day1_html = out_dir / "today_top25_weighbridge_core_sampling_manifest.html"
    generate_weighbridge_html(day1_df, day1_html)
    print(f"Saved Printable Weighbridge Manifest HTML: {day1_html.name}")

    print("\n" + "="*65)
    print("  ACTIVE LEARNING CORE-SAMPLER WEIGHBRIDGE PROTOCOL ACTIVE")
    print("="*65)
    print(f"Scheduled 60-Day Target:   1,500 Core Samples (25 trucks/day)")
    print(f"Day 1 Sampling Batch:      25 Trucks (100% Grade A Gold plots)")
    print(f"Villages Covered on Day 1: {day1_df['village'].nunique()} distinct village clusters")
    print(f"Varieties Represented:     {', '.join(day1_df['variety'].unique())}")
    print("="*65)


def generate_weighbridge_html(df: pd.DataFrame, out_path: Path):
    rows_html = ""
    for idx, r in df.reset_index(drop=True).iterrows():
        rows_html += f"""
        <tr>
            <td style="font-family:monospace;font-weight:700;">{r['core_sample_id']}</td>
            <td><strong>{r['plot_no']}</strong></td>
            <td>{r['farmer']}</td>
            <td>{r['village']}</td>
            <td><span class="pill-var">{r['variety']}</span> ({r['cane_type']})</td>
            <td>{r['crop_age_days']} d</td>
            <td style="color:#1e5a2f;font-weight:700;">{r['trust_score']}%</td>
            <td class="blank-col">&nbsp;</td>
            <td class="blank-col">&nbsp;</td>
            <td class="blank-col">&nbsp;</td>
            <td class="blank-col">&nbsp;</td>
            <td class="blank-col">&nbsp;</td>
        </tr>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Gangamai Sugar - Daily Core-Sampler Weighbridge Manifest (Day 1)</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; margin: 20px; color: #1a3c34; background: #fff; }}
.header {{ border-bottom: 2px solid #1a3c34; padding-bottom: 12px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: flex-end; }}
h1 {{ margin: 0 0 4px; font-size: 24px; font-family: Georgia, serif; }}
.sub {{ font-size: 12px; color: #55695f; margin: 0; }}
.badge {{ background: #e3f1d9; color: #1e5a2f; border: 1px solid #b3d7a1; padding: 4px 10px; border-radius: 4px; font-size: 12px; font-weight: 700; }}
table {{ width: 100%; border-collapse: collapse; font-size: 11px; }}
th {{ background: #eef2e7; color: #435449; text-transform: uppercase; font-size: 10px; letter-spacing: 0.5px; padding: 8px 6px; border: 1px solid #d4ded0; text-align: left; }}
td {{ padding: 8px 6px; border: 1px solid #d4ded0; }}
.blank-col {{ background: #fafcf8; width: 65px; border: 1px dashed #b5c7b0; text-align: center; }}
.pill-var {{ background: #e8eee2; padding: 2px 5px; border-radius: 3px; font-size: 10px; }}
.protocol-note {{ margin-top: 25px; padding: 15px; background: #f7f9f2; border: 1px solid #dbe2d4; border-radius: 5px; font-size: 11px; line-height: 1.6; }}
.signatures {{ margin-top: 30px; display: flex; justify-content: space-between; font-size: 12px; font-weight: 600; padding: 0 40px; }}
@media print {{ body {{ margin: 5mm; }} .header {{ border-bottom: 2px solid #000; }} }}
</style>
</head>
<body>

<div class="header">
  <div>
    <div style="font-size:10px;font-weight:700;letter-spacing:1px;color:#7a8a77;">GANGAMAI SUGAR · CANE QUALITY &amp; WEIGHBRIDGE CORE SAMPLING</div>
    <h1>Day 1 Weighbridge Core-Sampling Manifest (25 Target Trucks)</h1>
    <p class="sub">Active Learning Model Calibration Protocol · 100% Grade A Gold Plots</p>
  </div>
  <div style="text-align:right;">
    <span class="badge">SAMPLE DATE: DAY 1</span>
    <div style="font-size:10px;color:#666;margin-top:5px;">Target: 25 Core Samples</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th>Sample ID</th>
      <th>Plot No</th>
      <th>Farmer Name</th>
      <th>Village</th>
      <th>Variety / Crop</th>
      <th>Age</th>
      <th>Trust</th>
      <th style="background:#d9e8d3;">Arrival Time</th>
      <th style="background:#d9e8d3;">Core Brix (°Bx)</th>
      <th style="background:#d9e8d3;">Core Pol (%)</th>
      <th style="background:#d9e8d3;">Recovery (%)</th>
      <th style="background:#d9e8d3;">Delay (Hours)</th>
    </tr>
  </thead>
  <tbody>
    {rows_html}
  </tbody>
</table>

<div class="protocol-note">
  <strong>Standard Weighbridge Core-Sampling Protocol:</strong>
  <ol style="margin:6px 0 0;padding-left:20px;">
    <li>Insert hydraulic core-sampler at 45° angle through the middle-third of the cane truck bed.</li>
    <li>Express fresh composite juice within 10 minutes of coring; record refractometric Brix (°Bx).</li>
    <li>Perform lead-acetate / dry-clarification filtration and record polarimetric Pol (sucrose %).</li>
    <li>Enforce fundamental law: <em>Pol must be less than or equal to Brix</em>. If Pol > Brix, re-clean instrument prisms and repeat test.</li>
    <li>Record Cut-to-Crush delay hours from farmer cutting slip timestamp.</li>
  </ol>
</div>

<div class="signatures">
  <div>Weighbridge In-Charge Signature: _______________________</div>
  <div>Chief Laboratory Chemist Signature: _______________________</div>
</div>

</body>
</html>
"""
    out_path.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    generate_sampling_manifests()
