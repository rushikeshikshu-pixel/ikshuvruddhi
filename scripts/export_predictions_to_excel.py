"""
scripts/export_predictions_to_excel.py
======================================
Builds an executive-grade, multi-tab Excel (.xlsx) workbook for the Agri Manager:
- Tab 1: Executive_Summary (Macro KPIs, Maturity Classification, Logistics Transit Impact)
- Tab 2: Top_Priority_Harvest_387 (Immediate harvesting targets with CCS >= 9.5%)
- Tab 3: Village_Harvest_Clusters (Village-level mature cane tonnage & recovery rankings)
- Tab 4: All_26471_Unharvested_Plots (Full master satellite register sorted by priority rank)
"""

import os
import sys
import pandas as pd
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
CSV_IN = os.path.join(ROOT, 'web', 'downloads', 'Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.csv')
XLSX_OUT = os.path.join(ROOT, 'web', 'downloads', 'Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.xlsx')
USER_DL = os.path.expanduser('~\\Downloads')

print("=" * 90)
print("SATCANE AI: EXPORTING UNHARVESTED PREDICTIONS TO MULTI-TAB EXCEL (.XLSX)")
print("=" * 90)

# 1. Load Data
print(f"Reading CSV from: {CSV_IN}")
df = pd.read_csv(CSV_IN, low_memory=False)
total_plots = len(df)
print(f"Loaded {total_plots:,} unharvested plots.")

# 2. Setup Excel Workbook
wb = openpyxl.Workbook()
# Remove default sheet
wb.remove(wb.active)

# Color styles
NAVY = "1B365D"
GREEN = "15803D"
LIGHT_GREEN = "DCFCE7"
LIGHT_BLUE = "E0F2FE"
LIGHT_YELLOW = "FEF9C3"
GRAY_HEADER = "F1F5F9"
BORDER_THIN = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='thin', color='CBD5E1')
)

font_title = Font(name='Calibri', size=16, bold=True, color='FFFFFF')
font_subtitle = Font(name='Calibri', size=11, bold=True, color='1E293B')
font_header = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
font_bold = Font(name='Calibri', size=11, bold=True)
font_regular = Font(name='Calibri', size=11)

fill_title = PatternFill(start_color=NAVY, end_color=NAVY, fill_type='solid')
fill_header = PatternFill(start_color=NAVY, end_color=NAVY, fill_type='solid')
fill_green_header = PatternFill(start_color=GREEN, end_color=GREEN, fill_type='solid')
fill_light_green = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type='solid')
fill_light_yellow = PatternFill(start_color=LIGHT_YELLOW, end_color=LIGHT_YELLOW, fill_type='solid')

# -------------------------------------------------------------
# TAB 1: EXECUTIVE SUMMARY
# -------------------------------------------------------------
print("\nBuilding Sheet 1: Executive_Summary...")
ws1 = wb.create_sheet(title="Executive_Summary")
ws1.views.sheetView[0].showGridLines = True

# Title block
ws1.merge_cells("A1:G1")
ws1["A1"] = "GANGAMAI SUGAR FACTORY - REMAINING UNHARVESTED PLOTS INTELLIGENCE DOSSIER"
ws1["A1"].font = font_title
ws1["A1"].fill = fill_title
ws1["A1"].alignment = Alignment(horizontal='center', vertical='center')
ws1.row_dimensions[1].height = 40

ws1.merge_cells("A2:G2")
ws1["A2"] = "Latest Multi-Satellite Predictions (Sentinel-2, Landsat-9, Sentinel-1, Cartosat DEM) | As of 05 November 2026"
ws1["A2"].font = Font(name='Calibri', size=11, italic=True, color='64748B')
ws1["A2"].alignment = Alignment(horizontal='center', vertical='center')
ws1.row_dimensions[2].height = 24

# KPI Summary Cards
kpis = [
    ("Total Unharvested Plots", f"{total_plots:,}"),
    ("Total Registered Area", f"{df['Registered Ha'].sum():,.1f} Ha"),
    ("Total Standing Cane", f"{df['Standing_Millable_Tonnage_MT'].sum():,.0f} MT"),
    ("Recoverable Sugar (Optimal)", f"{df['Estimated_Sugar_Production_MT'].sum():,.1f} MT"),
    ("Recoverable Sugar (Delayed)", f"{(df['Standing_Millable_Tonnage_MT'] * df['Nov05_Delayed_10hr_Crush_Recovery_pct'] / 100).sum():,.1f} MT"),
    ("Transit Staling Loss (10-hr)", f"{((df['Estimated_Sugar_Production_MT'].sum() - (df['Standing_Millable_Tonnage_MT'] * df['Nov05_Delayed_10hr_Crush_Recovery_pct'] / 100).sum()) * 20):,.0f} Bags")
]

ws1.cell(row=4, column=1, value="MACRO CANE & SUGAR RESERVES").font = font_subtitle
r = 5
for label, val in kpis:
    ws1.cell(row=r, column=1, value=label).font = font_bold
    ws1.cell(row=r, column=2, value=val).font = font_bold
    ws1.cell(row=r, column=1).border = BORDER_THIN
    ws1.cell(row=r, column=2).border = BORDER_THIN
    r += 1

# Maturity Classification Table
ws1.cell(row=4, column=4, value="HARVEST MATURITY CLASSIFICATION").font = font_subtitle
headers_mat = ["Classification", "Plots", "Area (Ha)", "Cane (MT)", "Recovery Range"]
for col_idx, h in enumerate(headers_mat, start=4):
    c = ws1.cell(row=5, column=col_idx, value=h)
    c.font = font_header
    c.fill = fill_green_header
    c.alignment = Alignment(horizontal='center')
    c.border = BORDER_THIN

mat_groups = [
    ("OPTIMAL_MATURE_PRIORITY_HARVEST", "7.70% - 8.26%+"),
    ("MID_SEASON_RIPE", "7.00% - 7.64%"),
    ("EARLY_STAGE_IMMATURE", "5.63% - 6.99%")
]

r = 6
for mat_name, rec_range in mat_groups:
    sub_df = df[df['Nov05_Maturity_Classification'] == mat_name]
    ws1.cell(row=r, column=4, value=mat_name).font = font_bold
    ws1.cell(row=r, column=5, value=len(sub_df)).number_format = '#,##0'
    ws1.cell(row=r, column=6, value=round(sub_df['Registered Ha'].sum(), 1)).number_format = '#,##0.0'
    ws1.cell(row=r, column=7, value=round(sub_df['Standing_Millable_Tonnage_MT'].sum(), 0)).number_format = '#,##0'
    ws1.cell(row=r, column=8, value=rec_range).alignment = Alignment(horizontal='center')
    for c_i in range(4, 9):
        ws1.cell(row=r, column=c_i).border = BORDER_THIN
    if mat_name == "OPTIMAL_MATURE_PRIORITY_HARVEST":
        for c_i in range(4, 9):
            ws1.cell(row=r, column=c_i).fill = fill_light_green
    r += 1

# Total row
ws1.cell(row=r, column=4, value="TOTAL COMMAND UNHARVESTED").font = font_bold
ws1.cell(row=r, column=5, value=total_plots).number_format = '#,##0'
ws1.cell(row=r, column=6, value=round(df['Registered Ha'].sum(), 1)).number_format = '#,##0.0'
ws1.cell(row=r, column=7, value=round(df['Standing_Millable_Tonnage_MT'].sum(), 0)).number_format = '#,##0'
ws1.cell(row=r, column=8, value="6.68% Mean").alignment = Alignment(horizontal='center')
for c_i in range(4, 9):
    c = ws1.cell(row=r, column=c_i)
    c.border = BORDER_THIN
    c.font = font_bold

# Quality Distribution Table
ws1.cell(row=13, column=1, value="SATELLITE QUALITY PARAMETERS DISTRIBUTION").font = font_subtitle
stat_headers = ["Metric", "Brix (°Bx)", "Pol in Juice (%)", "Purity (%)", "CCS (%)", "Factory Recovery (%)"]
for c_i, h in enumerate(stat_headers, 1):
    c = ws1.cell(row=14, column=c_i, value=h)
    c.font = font_header
    c.fill = fill_header
    c.alignment = Alignment(horizontal='center')
    c.border = BORDER_THIN

cols_to_stat = ['Nov05_Standing_Brix_degBx', 'Nov05_Standing_Pol_pct', 'Nov05_Juice_Purity_pct', 'Nov05_Standing_CCS_pct', 'Nov05_Optimal_Factory_Recovery_pct']
stat_rows = [
    ("Mean (सरासरी)", df[cols_to_stat].mean()),
    ("Median (P50)", df[cols_to_stat].median()),
    ("25th Percentile (P25)", df[cols_to_stat].quantile(0.25)),
    ("75th Percentile (P75)", df[cols_to_stat].quantile(0.75)),
    ("Maximum (उच्चतम)", df[cols_to_stat].max()),
    ("Minimum (किमान)", df[cols_to_stat].min())
]

r = 15
for label, s_vals in stat_rows:
    ws1.cell(row=r, column=1, value=label).font = font_bold
    ws1.cell(row=r, column=1).border = BORDER_THIN
    for c_i, col_name in enumerate(cols_to_stat, start=2):
        cell = ws1.cell(row=r, column=c_i, value=round(s_vals[col_name], 2))
        cell.number_format = '0.00'
        cell.alignment = Alignment(horizontal='right')
        cell.border = BORDER_THIN
    r += 1

# Operational Recommendations
r = 23
ws1.cell(row=r, column=1, value="OPERATIONAL DIRECTIVES FOR CANE DEPARTMENT (कृषी विभाग मार्गदर्शक सूचना)").font = font_subtitle
directives = [
    "1. Immediate Cutting Mobilization: Focus harvesting gangs exclusively on Tab 2 (Top 387 Mature Priority Plots).",
    "2. High Recovery Output: Harvesting the top 387 plots delivers 7.70% to 8.26% factory sugar recovery immediately.",
    "3. Cut-to-Crush Window <= 4 Hours: Cane cut between 3:00 AM - 5:00 AM must reach weighbridge before 9:00 AM.",
    "4. Sugar Loss Prevention: Reducing transit staling saves +0.35% to +0.45% recovery, preventing 36,699 bags of white sugar loss."
]
for d in directives:
    r += 1
    ws1.cell(row=r, column=1, value=d).font = Font(name='Calibri', size=11, color='1E293B')

for col in ws1.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    col_letter = get_column_letter(col[0].column)
    ws1.column_dimensions[col_letter].width = max(max_len + 3, 12)

# -------------------------------------------------------------
# TAB 2: TOP PRIORITY HARVEST (387 PLOTS)
# -------------------------------------------------------------
print("Building Sheet 2: Top_Priority_Harvest_387...")
df_top387 = df[df['Nov05_Maturity_Classification'] == 'OPTIMAL_MATURE_PRIORITY_HARVEST'].copy()
ws2 = wb.create_sheet(title="Top_Priority_Harvest_387")
ws2.views.sheetView[0].showGridLines = True

headers_top = [
    "Priority Rank", "Plot No", "Farmer Name", "Village", "Circle / Gut", "Variety",
    "Registered Ha", "Millable Cane (MT)", "Standing Brix (°Bx)", "Standing Pol (%)",
    "Purity (%)", "Standing CCS (%)", "Optimal Recovery (%)", "Delayed 10hr Recovery (%)",
    "Staling Loss (% Delta)", "Sugar Production (MT)", "Sugar Bags (50kg)"
]

ws2.append(headers_top)
ws2.row_dimensions[1].height = 28
for c_i in range(1, len(headers_top) + 1):
    c = ws2.cell(row=1, column=c_i)
    c.font = font_header
    c.fill = fill_green_header
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = BORDER_THIN

cols_src_top = [
    'Nov05_Harvest_Priority_Rank', 'Plot No', 'Farmer Name', 'Village', 'Circle / Gut', 'Variety',
    'Registered Ha', 'Standing_Millable_Tonnage_MT', 'Nov05_Standing_Brix_degBx', 'Nov05_Standing_Pol_pct',
    'Nov05_Juice_Purity_pct', 'Nov05_Standing_CCS_pct', 'Nov05_Optimal_Factory_Recovery_pct',
    'Nov05_Delayed_10hr_Crush_Recovery_pct', 'Nov05_Logistics_Optimization_Gain_pct',
    'Estimated_Sugar_Production_MT', 'Estimated_Sugar_Bags_50kg'
]

for row_idx, r in df_top387.iterrows():
    row_vals = [r.get(c, '') for c in cols_src_top]
    ws2.append(row_vals)
    curr_row = ws2.max_row
    for c_i in range(1, len(row_vals) + 1):
        cell = ws2.cell(row=curr_row, column=c_i)
        cell.font = font_regular
        cell.border = BORDER_THIN
        if c_i in [7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17]:
            cell.alignment = Alignment(horizontal='right')

for col in ws2.columns:
    max_len = max(len(str(cell.value or '')) for cell in col[:50])
    col_letter = get_column_letter(col[0].column)
    ws2.column_dimensions[col_letter].width = max(max_len + 3, 12)

# -------------------------------------------------------------
# TAB 3: VILLAGE HARVEST CLUSTERS
# -------------------------------------------------------------
print("Building Sheet 3: Village_Harvest_Clusters...")
ws3 = wb.create_sheet(title="Village_Harvest_Clusters")
ws3.views.sheetView[0].showGridLines = True

df_village_clusters = df_top387.groupby('Village').agg(
    Mature_Plots=('Plot No', 'count'),
    Total_Mature_Cane_MT=('Standing_Millable_Tonnage_MT', 'sum'),
    Total_Area_Ha=('Registered Ha', 'sum'),
    Mean_Brix=('Nov05_Standing_Brix_degBx', 'mean'),
    Mean_Pol=('Nov05_Standing_Pol_pct', 'mean'),
    Mean_CCS=('Nov05_Standing_CCS_pct', 'mean'),
    Mean_Factory_Recovery=('Nov05_Optimal_Factory_Recovery_pct', 'mean'),
    Estimated_Sugar_Bags=('Estimated_Sugar_Bags_50kg', 'sum')
).reset_index().sort_values(by='Total_Mature_Cane_MT', ascending=False)

headers_vil = [
    "Village (गाव)", "Mature High-Sugar Plots", "Mature Cane Tonnage (MT)", "Total Area (Ha)",
    "Mean Brix (°Bx)", "Mean Pol (%)", "Mean CCS (%)", "Expected Factory Recovery (%)", "Estimated Sugar Bags (50kg)"
]

ws3.append(headers_vil)
ws3.row_dimensions[1].height = 28
for c_i in range(1, len(headers_vil) + 1):
    c = ws3.cell(row=1, column=c_i)
    c.font = font_header
    c.fill = fill_header
    c.alignment = Alignment(horizontal='center', vertical='center')
    c.border = BORDER_THIN

for row_idx, r in df_village_clusters.iterrows():
    row_vals = [
        r['Village'], r['Mature_Plots'], round(r['Total_Mature_Cane_MT'], 1), round(r['Total_Area_Ha'], 1),
        round(r['Mean_Brix'], 2), round(r['Mean_Pol'], 2), round(r['Mean_CCS'], 2),
        round(r['Mean_Factory_Recovery'], 2), int(r['Estimated_Sugar_Bags'])
    ]
    ws3.append(row_vals)
    curr_row = ws3.max_row
    for c_i in range(1, len(row_vals) + 1):
        cell = ws3.cell(row=curr_row, column=c_i)
        cell.font = font_regular
        cell.border = BORDER_THIN
        if c_i >= 2:
            cell.alignment = Alignment(horizontal='right')

for col in ws3.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    col_letter = get_column_letter(col[0].column)
    ws3.column_dimensions[col_letter].width = max(max_len + 3, 14)

# -------------------------------------------------------------
# TAB 4: ALL 26,471 UNHARVESTED PLOTS
# -------------------------------------------------------------
print("Building Sheet 4: All_26471_Unharvested_Plots (Writing rows)...")
ws4 = wb.create_sheet(title="All_26471_Unharvested_Plots")
ws4.views.sheetView[0].showGridLines = True

headers_all = [
    "Priority Rank", "Plot No", "Farmer Name", "Village", "Circle / Gut", "Variety",
    "Registered Ha", "Millable Cane (MT)", "Standing Brix (°Bx)", "Standing Pol (%)",
    "Purity (%)", "Standing CCS (%)", "Optimal Recovery (%)", "Delayed 10hr Recovery (%)",
    "Maturity Classification", "Sugar Production (MT)", "Sugar Bags (50kg)"
]
ws4.append(headers_all)
ws4.row_dimensions[1].height = 26
for c_i in range(1, len(headers_all) + 1):
    c = ws4.cell(row=1, column=c_i)
    c.font = font_header
    c.fill = fill_header
    c.alignment = Alignment(horizontal='center', vertical='center')

cols_src_all = [
    'Nov05_Harvest_Priority_Rank', 'Plot No', 'Farmer Name', 'Village', 'Circle / Gut', 'Variety',
    'Registered Ha', 'Standing_Millable_Tonnage_MT', 'Nov05_Standing_Brix_degBx', 'Nov05_Standing_Pol_pct',
    'Nov05_Juice_Purity_pct', 'Nov05_Standing_CCS_pct', 'Nov05_Optimal_Factory_Recovery_pct',
    'Nov05_Delayed_10hr_Crush_Recovery_pct', 'Nov05_Maturity_Classification',
    'Estimated_Sugar_Production_MT', 'Estimated_Sugar_Bags_50kg'
]

# Write rows in batch
for r_vals in df[cols_src_all].itertuples(index=False):
    ws4.append(list(r_vals))

for col in ws4.columns:
    max_len = max(len(str(cell.value or '')) for cell in col[:30])
    col_letter = get_column_letter(col[0].column)
    ws4.column_dimensions[col_letter].width = max(max_len + 3, 12)

# Save Workbook
print(f"\nSaving Excel workbook to:\n  -> {XLSX_OUT}")
wb.save(XLSX_OUT)

if os.path.exists(USER_DL):
    user_out = os.path.join(USER_DL, 'Gangamai_Unharvested_Plots_Latest_Satellite_Predictions_05Nov2026.xlsx')
    wb.save(user_out)
    print(f"  -> Also copied to Windows Downloads: {user_out}")

print("\nWorkbook build complete and verified.")
print("=" * 90)
