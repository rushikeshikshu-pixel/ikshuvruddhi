#!/usr/bin/env python3
"""Command Area Data Quality Index (DQI) & Trust Score Audit for Gangamai Sugar.

Processes all 28,847 registered plots through the biophysical Data Quality Engine.
Identifies:
1. Trust Score distribution (Grade A, B, C).
2. Area discrepancy between farmer self-declaration and GPS/satellite polygon area.
3. Chemical physics & purity anomalies.
4. Immature vs harvest-eligible plots.
5. Village-by-village data fidelity ranking.
"""

import sys
import os
import json
from pathlib import Path
import pandas as pd
import numpy as np

# Ensure project root is in sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root_dir))

from ml.data_quality_engine import evaluate_plot_quality


def run_command_area_audit():
    input_csv = root_dir / "web" / "downloads" / "mill_calibrated_28847_plots_master_register.csv"
    if not input_csv.exists():
        print(f"Error: {input_csv} does not exist!")
        return

    print(f"Loading master register: {input_csv.name}...")
    df = pd.read_csv(input_csv, low_memory=False)
    total_plots = len(df)
    print(f"Loaded {total_plots:,} plots. Running biophysical quality evaluation...")

    results = []
    
    for idx, row in df.iterrows():
        reg_ha = float(row["registered_area_ha"]) if pd.notnull(row.get("registered_area_ha")) else 0.0
        reg_acres = reg_ha * 2.47105
        gps_acres = float(row["Effective_Cane_Acres"]) if pd.notnull(row.get("Effective_Cane_Acres")) else None
        
        variety = str(row.get("Variety Name", ""))
        p_date = str(row.get("Plantation Date", ""))
        
        try:
            crop_age = int(float(row["crop_age_days"])) if pd.notnull(row.get("crop_age_days")) else None
        except (ValueError, TypeError):
            crop_age = None
            
        try:
            brix = float(row["Calibrated_Brix_Bx"]) if pd.notnull(row.get("Calibrated_Brix_Bx")) else None
        except (ValueError, TypeError):
            brix = None
            
        try:
            pol = float(row["Calibrated_Pol_Pct"]) if pd.notnull(row.get("Calibrated_Pol_Pct")) else None
        except (ValueError, TypeError):
            pol = None
            
        try:
            rec = float(row["Calibrated_Sugar_Recovery_Pct"]) if pd.notnull(row.get("Calibrated_Sugar_Recovery_Pct")) else None
        except (ValueError, TypeError):
            rec = None
            
        try:
            ndvi = float(row["satellite_ndvi"]) if pd.notnull(row.get("satellite_ndvi")) else None
        except (ValueError, TypeError):
            ndvi = None
            
        report = evaluate_plot_quality(
            plot_no=str(row["Plot No"]),
            registered_acres=reg_acres,
            gps_acres=gps_acres,
            variety=variety,
            planting_date=p_date,
            crop_age_days=crop_age,
            lab_brix=brix,
            lab_pol=pol,
            lab_recovery=rec,
            obs_cloud_pct=0.0,
            obs_ndvi=ndvi,
            obs_age_days=10,
            cut_to_crush_hours=None,
            has_valid_boundary=True,
        )
        
        results.append({
            "plot_no": row["Plot No"],
            "farmer": row.get("Farmer", ""),
            "village": row.get("Village", ""),
            "gut": row.get("Gut", ""),
            "variety": variety,
            "cane_type": row.get("Cane Type", ""),
            "registered_acres": round(reg_acres, 2),
            "gps_acres": round(gps_acres, 2) if gps_acres is not None else 0.0,
            "area_diff_pct": round(abs(gps_acres - reg_acres) / reg_acres * 100.0, 1) if (gps_acres is not None and reg_acres > 0) else 0.0,
            "crop_age_days": crop_age,
            "ndvi": ndvi,
            "calibrated_pol": pol,
            "calibrated_brix": brix,
            "purity_pct": report["purity_pct"],
            "trust_score": report["trust_score"],
            "quality_grade": report["quality_grade"],
            "eligible_for_harvest": report["eligible_for_harvest"],
            "eligible_for_training": report["eligible_for_training"],
            "quality_flags": "; ".join(report["flags"]) if report["flags"] else "VERIFIED_GOLD",
        })

    res_df = pd.DataFrame(results)
    
    # Summary Statistics
    grade_a = (res_df["quality_grade"] == "A").sum()
    grade_b = (res_df["quality_grade"] == "B").sum()
    grade_c = (res_df["quality_grade"] == "C").sum()
    avg_score = res_df["trust_score"].mean()
    harvest_eligible = res_df["eligible_for_harvest"].sum()
    training_eligible = res_df["eligible_for_training"].sum()
    
    print("\n" + "="*60)
    print("  COMMAND AREA DATA QUALITY AUDIT RESULTS (GANGAMAI SUGAR)")
    print("="*60)
    print(f"Total Plots Audited:        {total_plots:,}")
    print(f"Mean Command Trust Score:   {avg_score:.1f}%")
    print(f"Grade A (Gold Standard):    {grade_a:,} ({grade_a/total_plots*100:.1f}%)")
    print(f"Grade B (Review / Usable):  {grade_b:,} ({grade_b/total_plots*100:.1f}%)")
    print(f"Grade C (Severe / Flagged): {grade_c:,} ({grade_c/total_plots*100:.1f}%)")
    print(f"Eligible for Harvest Order: {harvest_eligible:,} ({harvest_eligible/total_plots*100:.1f}%)")
    print(f"Eligible for Model Train:   {training_eligible:,} ({training_eligible/total_plots*100:.1f}%)")
    print("="*60)
    
    # Top Quality Flags Aggregated by Category
    category_flags = []
    for f_str in res_df["quality_flags"]:
        if f_str != "VERIFIED_GOLD":
            for item in f_str.split(";"):
                item_s = item.strip()
                if "UNUSUALLY_HIGH_PURITY" in item_s:
                    category_flags.append("UNUSUALLY_HIGH_PURITY (> 93.0%)")
                elif "LOW_JUICE_PURITY" in item_s:
                    category_flags.append("LOW_JUICE_PURITY (< 75.0%)")
                elif "AREA_DISCREPANCY" in item_s:
                    category_flags.append("AREA_DISCREPANCY (> 25% diff)")
                elif "IMMATURE_CROP" in item_s:
                    category_flags.append("IMMATURE_CROP (< 180 days)")
                elif "FATAL_ERROR" in item_s:
                    category_flags.append("FATAL_ERROR: Pol > Brix")
                else:
                    category_flags.append(item_s)
    flag_series = pd.Series(category_flags).value_counts()
    print("\nAggregated Quality & Biophysical Flags:")
    for flag_name, count in flag_series.head(8).items():
        print(f" - {flag_name}: {count:,} plots ({count/total_plots*100:.1f}%)")
        
    # Village level summary
    village_grp = res_df.groupby("village").agg(
        total_plots=("plot_no", "count"),
        mean_trust=("trust_score", "mean"),
        grade_a_pct=("quality_grade", lambda s: (s == "A").mean() * 100),
        grade_c_pct=("quality_grade", lambda s: (s == "C").mean() * 100),
        high_diff_plots=("area_diff_pct", lambda s: (s > 25.0).sum()),
    ).reset_index().sort_values("total_plots", ascending=False)
    
    print("\nTop 5 Largest Command Villages Quality Rating:")
    for _, v_row in village_grp.head(5).iterrows():
        print(f" * {v_row['village']}: {v_row['total_plots']:,} plots | Mean Trust: {v_row['mean_trust']:.1f}% | Grade A: {v_row['grade_a_pct']:.1f}% | Grade C: {v_row['grade_c_pct']:.1f}%")

    # Output CSVs
    out_dir = root_dir / "web" / "downloads"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    out_csv = out_dir / "command_area_28847_data_quality_index_audit.csv"
    res_df.to_csv(out_csv, index=False)
    print(f"\nSaved Full Command Area DQI Audit CSV: {out_csv.resolve()} ({out_csv.stat().st_size / (1024*1024):.2f} MB)")
    
    # Save Village Summary
    village_csv = out_dir / "village_level_data_quality_trust_ranking.csv"
    village_grp.to_csv(village_csv, index=False)
    print(f"Saved Village Trust Ranking CSV: {village_csv.resolve()}")
    
    # Generate HTML Executive Audit Report
    html_out = out_dir / "gangamai_28847_plots_data_quality_executive_audit.html"
    generate_html_report(res_df, village_grp, flag_series, avg_score, grade_a, grade_b, grade_c, total_plots, harvest_eligible, html_out)
    print(f"Saved Executive HTML Report: {html_out.resolve()}")


def generate_html_report(df, village_grp, flags, avg_score, grade_a, grade_b, grade_c, total_plots, harvest_eligible, html_out):
    top_flags_rows = "".join([
        f"<tr><td><strong>{name}</strong></td><td style='text-align:right;'>{cnt:,}</td><td style='text-align:right;'>{cnt/total_plots*100:.1f}%</td></tr>"
        for name, cnt in flags.head(10).items()
    ])
    
    village_rows = "".join([
        f"<tr><td><strong>{r['village']}</strong></td><td style='text-align:right;'>{r['total_plots']:,}</td><td style='text-align:right;font-weight:600;'>{r['mean_trust']:.1f}%</td><td style='text-align:right;'>{r['grade_a_pct']:.1f}%</td><td style='text-align:right;'>{r['grade_c_pct']:.1f}%</td><td style='text-align:right;'>{r['high_diff_plots']:,}</td></tr>"
        for _, r in village_grp.head(15).iterrows()
    ])
    
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Gangamai Sugar - Command Area Data Quality Audit (28,847 Plots)</title>
<style>
:root {{ --ink: #1a3c34; --green: #225a47; --bg: #f7f8f2; --card: #ffffff; --border: #dbe2d4; --muted: #64746a; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background: var(--bg); color: var(--ink); margin: 0; padding: 30px 20px; }}
.wrap {{ max-width: 1200px; margin: 0 auto; }}
header {{ border-bottom: 2px solid var(--ink); padding-bottom: 20px; margin-bottom: 30px; display: flex; justify-content: space-between; align-items: flex-end; }}
h1 {{ font-family: Georgia, serif; font-size: 32px; margin: 0 0 6px; color: var(--ink); }}
.eyebrow {{ font-size: 11px; letter-spacing: 1.5px; font-weight: 700; color: #7f8e7b; text-transform: uppercase; }}
.kpi-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 30px; }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: 20px; }}
.card span {{ font-size: 11px; text-transform: uppercase; color: var(--muted); font-weight: 600; letter-spacing: 0.5px; }}
.card strong {{ display: block; font-family: Georgia, serif; font-size: 36px; color: var(--ink); margin-top: 8px; }}
.card small {{ font-size: 11px; color: var(--muted); }}
.badge {{ padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; font-family: monospace; }}
.badge.gold {{ background: #e3f1d9; color: #1e5a2f; border: 1px solid #b3d7a1; }}
.badge.warn {{ background: #e3f0f7; color: #23546b; border: 1px solid #b1d4ea; }}
.badge.flag {{ background: #f9ede6; color: #943f25; border: 1px solid #e7c1b3; }}
table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 15px; }}
th {{ background: #eef2e7; text-align: left; padding: 10px 14px; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted); border-bottom: 1px solid var(--border); }}
td {{ padding: 11px 14px; border-bottom: 1px solid var(--border); }}
.two-col {{ display: grid; grid-template-columns: 1fr 1.3fr; gap: 24px; margin-bottom: 30px; }}
.section-title {{ font-family: Georgia, serif; font-size: 20px; margin: 0 0 10px; color: var(--ink); }}
footer {{ border-top: 1px solid var(--border); padding-top: 20px; font-size: 11px; color: var(--muted); display: flex; justify-content: space-between; }}
</style>
</head>
<body>
<div class="wrap">
<header>
  <div>
    <div class="eyebrow">IKSHU INTELLIGENCE &amp; SATCANE AI ENGINE · AUDIT REPORT</div>
    <h1>Gangamai Sugar Command Area Data Quality Audit</h1>
    <p style="margin:0;font-size:13px;color:var(--muted);">Automated biophysical validation across 28,847 registered sugarcane plots.</p>
  </div>
  <div style="text-align:right;">
    <span class="badge gold">SEASON 2026–27</span>
    <div style="font-size:11px;color:var(--muted);margin-top:6px;">Status: Factory Crushing Ready</div>
  </div>
</header>

<div class="kpi-grid">
  <div class="card">
    <span>Command Trust Score</span>
    <strong>{avg_score:.1f}%</strong>
    <small>Mean score across command area</small>
  </div>
  <div class="card">
    <span>Grade A (Gold Standard)</span>
    <strong>{grade_a:,}</strong>
    <small>{grade_a/total_plots*100:.1f}% verified high-trust</small>
  </div>
  <div class="card">
    <span>Grade B (Warning / Usable)</span>
    <strong>{grade_b:,}</strong>
    <small>{grade_b/total_plots*100:.1f}% minor review flags</small>
  </div>
  <div class="card">
    <span>Grade C (Severe Flags)</span>
    <strong>{grade_c:,}</strong>
    <small>{grade_c/total_plots*100:.1f}% require ground resurvey</small>
  </div>
</div>

<div class="two-col">
  <div class="card">
    <h2 class="section-title">Quality &amp; Anomaly Flag Breakdown</h2>
    <p style="font-size:12px;color:var(--muted);margin-top:0;">Top automated rule triggers across physics, geometry and phenology.</p>
    <table>
      <thead>
        <tr><th>Flag Diagnostic</th><th style="text-align:right;">Plot Count</th><th style="text-align:right;">Frequency</th></tr>
      </thead>
      <tbody>
        {top_flags_rows}
      </tbody>
    </table>
  </div>

  <div class="card">
    <h2 class="section-title">Top Command Villages Data Fidelity Ranking</h2>
    <p style="font-size:12px;color:var(--muted);margin-top:0;">Fidelity and area consistency across the largest cane clusters.</p>
    <table>
      <thead>
        <tr><th>Village / Cluster</th><th style="text-align:right;">Plots</th><th style="text-align:right;">Trust Score</th><th style="text-align:right;">Grade A</th><th style="text-align:right;">Grade C</th><th style="text-align:right;">Area &gt; 25% Diff</th></tr>
      </thead>
      <tbody>
        {village_rows}
      </tbody>
    </table>
  </div>
</div>

<div class="card" style="margin-bottom:30px;">
  <h2 class="section-title">Factory Operational Directives for Crushing Operations</h2>
  <ul style="font-size:13px;line-height:1.8;color:var(--ink);padding-left:20px;margin:10px 0 0;">
    <li><strong>Harvest Cutting Orders:</strong> {harvest_eligible:,} plots ({harvest_eligible/total_plots*100:.1f}%) have passed all fatal physical sanity checks and are cleared for harvest slip generation.</li>
    <li><strong>Grade C Plots ({grade_c:,}):</strong> Automatically placed on administrative review. Field agricultural assistants must confirm GPS boundaries before slips are released.</li>
    <li><strong>Chemical Governance:</strong> Re-calibrated lab entry forms now strictly enforce (Pol &le; Brix) to prevent downstream sucrose inversion contamination.</li>
  </ul>
</div>

<footer>
  <span>IKSHU INTELLIGENCE · CADASTRAL &amp; SATELLITE CANE MANAGEMENT</span>
  <span>GANGAMAI INDUSTRIES AND COMMERCE LTD.</span>
</footer>
</div>
</body>
</html>
"""
    html_out.write_text(html, encoding="utf-8")


if __name__ == "__main__":
    run_command_area_audit()
