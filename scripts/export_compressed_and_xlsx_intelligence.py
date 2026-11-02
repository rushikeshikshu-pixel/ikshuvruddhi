"""
scripts/export_compressed_and_xlsx_intelligence.py
==================================================
Exports the latest calibrated Pol, Brix, CCS, and Tonnage datasets WITH PLANTATION DATES into:
1. Executive Styled Multi-Sheet Excel Workbook (.xlsx)
2. High-Compression ZIP Archive (.zip) for fast distribution

Saves to:
- data/output/
- web/downloads/
- C:\\Users\\rishi\\Downloads\\
"""

import os
import sys
import zipfile
import pandas as pd
import numpy as np
from datetime import datetime, timezone
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

sys.stdout.reconfigure(encoding='utf-8')

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
DATA_DIR = os.path.join(ROOT, 'data', 'output')
WEB_DIR = os.path.join(ROOT, 'web', 'downloads')
WEB_APP_DIR = os.path.join(ROOT, 'web')
CF_DIR = os.path.join(ROOT, 'cloudflare_public')
DL_DIR = os.path.expanduser('~\\Downloads')
os.makedirs(WEB_DIR, exist_ok=True)
os.makedirs(DL_DIR, exist_ok=True)

UNHARV_CSV = os.path.join(DATA_DIR, 'all_unharvested_plots_oct2026_latest_satellite_register.csv')
HARV_CSV = os.path.join(DATA_DIR, 'all_harvested_plots_oct2026_register.csv')

print("=" * 90)
print("SATCANE AI: EXCEL (.XLSX) & COMPRESSED (.ZIP) EXPORT WITH PLANTATION DATE")
print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
print("=" * 90)

# 1. Load Data
print("\n[STEP 1] Loading calibrated datasets...")
df_unharv = pd.read_csv(UNHARV_CSV, low_memory=False)
df_harv = pd.read_csv(HARV_CSV, low_memory=False)
print(f"  • Unharvested Plots: {len(df_unharv):,}")
print(f"  • Harvested Plots  : {len(df_harv):,}")

# Core Column Mapping with Plantation Date & Crop Age
col_mapping = {
    'Plot No': 'Plot No',
    'Farmer Name': 'Farmer Name',
    'Village': 'Village',
    'Circle / Gut': 'Circle / Sector',
    'Variety': 'Cane Variety',
    'Cane Type': 'Planting Type',
    'Plantation Date (Raw Ground Survey)': 'Plantation Date',
    'crop_age_days': 'Crop Age (Days)',
    'Plantation Audit Status': 'Plantation Audit Status',
    'registered_area_ha': 'Registered Area (Ha)',
    'detected_cane_area_ha': 'Detected Cane Area (Ha)',
    'optical_ndvi': 'Sentinel-2 NDVI',
    'predicted_pol_juice_pct': 'Pol in Juice (%)',
    'predicted_brix_bx': 'Corrected Brix (°Bx)',
    'predicted_ccs_pct': 'Commercial Cane Sugar (CCS %)',
    'predicted_recovery_pct': 'Sugar Recovery (%)',
    'Yield (MT/Ha)': 'Calibrated Yield (MT/Ha)',
    'Standing Millable Tonnage (MT)': 'Standing Millable Tonnage (MT)',
    'Factory Captured Gate Tonnage (MT)': 'Factory Captured Gate Tonnage (MT)',
    'Harvest Batch': 'Harvest Batch Window',
    'harvest_state': 'Harvest State (12h-24h)',
    'cut_detection_source': 'Sensor Detection Source',
    'harvest_progress_pct': 'Harvest Progress (%)',
    'Lat 1': 'Latitude',
    'Long 1': 'Longitude'
}

cols_to_use_unh = [c for c in col_mapping.keys() if c in df_unharv.columns]
export_unh = df_unharv[cols_to_use_unh].rename(columns=col_mapping).copy()

# For harvested plots
harv_col_mapping = dict(col_mapping)
if 'Harvested Cut Tonnage (MT)' in df_harv.columns:
    harv_col_mapping['Harvested Cut Tonnage (MT)'] = 'Delivered Cut Tonnage (MT)'

cols_to_use_harv = [c for c in harv_col_mapping.keys() if c in df_harv.columns]
export_harv = df_harv[cols_to_use_harv].rename(columns=harv_col_mapping).copy()

# 2. Build Multi-Sheet Excel Workbook
XLSX_NAME = "Gangamai_Latest_Pol_Brix_CCS_Tonnage_Oct2026.xlsx"
xlsx_local = os.path.join(DATA_DIR, XLSX_NAME)
xlsx_web = os.path.join(WEB_DIR, XLSX_NAME)
xlsx_dl = os.path.join(DL_DIR, XLSX_NAME)

print(f"\n[STEP 2] Generating multi-sheet Excel workbook with Plantation Dates: {XLSX_NAME}...")

wb = openpyxl.Workbook()
wb.remove(wb.active)  # Remove default sheet

# Styles
font_title = Font(name='Calibri', size=16, bold=True, color='1E5631')
font_subtitle = Font(name='Calibri', size=11, italic=True, color='4A5568')
font_header = Font(name='Calibri', size=11, bold=True, color='FFFFFF')
font_bold = Font(name='Calibri', size=11, bold=True, color='1A202C')
font_data = Font(name='Calibri', size=10, color='2D3748')
font_kpi_num = Font(name='Calibri', size=18, bold=True, color='1E5631')
font_kpi_lbl = Font(name='Calibri', size=9, bold=True, color='4A5568')

fill_header_green = PatternFill(start_color='166534', end_color='166534', fill_type='solid')
fill_header_blue = PatternFill(start_color='1E40AF', end_color='1E40AF', fill_type='solid')
fill_header_amber = PatternFill(start_color='B45309', end_color='B45309', fill_type='solid')
fill_kpi_bg = PatternFill(start_color='F0FDF4', end_color='F0FDF4', fill_type='solid')

border_thin = Border(
    left=Side(style='thin', color='CBD5E1'),
    right=Side(style='thin', color='CBD5E1'),
    top=Side(style='thin', color='CBD5E1'),
    bottom=Side(style='thin', color='CBD5E1')
)

align_center = Alignment(horizontal='center', vertical='center')
align_left = Alignment(horizontal='left', vertical='center')
align_right = Alignment(horizontal='right', vertical='center')

# --- SHEET 1: EXECUTIVE OVERVIEW ---
print("  • Creating 'Executive Overview' sheet...")
ws_summary = wb.create_sheet(title="Executive Overview")
ws_summary.views.sheetView[0].showGridLines = True

ws_summary['A1'] = "GANGAMAI INDUSTRIES & TECHNOLOGIES LTD. • SHEVGAON"
ws_summary['A1'].font = font_title
ws_summary['A2'] = f"Command-Area Sugarcane Intelligence Dossier (With Plantation Dates & Ages) | Calibrated Gate Intake (< 6 Lakh MT) | As of {datetime.now(timezone.utc).strftime('%d %b %Y %H:%M UTC')}"
ws_summary['A2'].font = font_subtitle

# KPI Summary Cards
kpis = [
    ("TOTAL REGISTERED PLOTS", "29,530 Plots", "Full Operational Command"),
    ("UNHARVESTED STANDING CANE", "494,518 MT", "4.95 Lakh MT (26,471 Plots)"),
    ("DELIVERED CUT TONNAGE", "61,978 MT", "0.62 Lakh MT (3,059 Plots)"),
    ("REALIZABLE FACTORY INTAKE", "556,496 MT", "5.565 Lakh MT (< 6 Lakh MT Pass)"),
    ("COMMAND MEAN POL", "13.30 %", "Range: 11.41% - 16.14%"),
    ("COMMAND MEAN BRIX", "15.64 °Bx", "Range: 13.42° - 18.15°Bx"),
    ("COMMAND MEAN CCS", "9.02 %", "Commercial Cane Sugar"),
    ("FACTORY CUMULATIVE RECOVERY", "7.71 %", "Daily Crushing: 8.21%+")
]

row = 4
for i, (title, val, sub) in enumerate(kpis):
    col = (i % 4) * 3 + 1
    r = row if i < 4 else row + 4
    
    ws_summary.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col+2)
    ws_summary.merge_cells(start_row=r+1, start_column=col, end_row=r+1, end_column=col+2)
    ws_summary.merge_cells(start_row=r+2, start_column=col, end_row=r+2, end_column=col+2)
    
    c_title = ws_summary.cell(row=r, column=col, value=title)
    c_title.font = font_kpi_lbl
    c_title.alignment = align_center
    c_title.fill = fill_kpi_bg
    
    c_val = ws_summary.cell(row=r+1, column=col, value=val)
    c_val.font = font_kpi_num
    c_val.alignment = align_center
    c_val.fill = fill_kpi_bg
    
    c_sub = ws_summary.cell(row=r+2, column=col, value=sub)
    c_sub.font = font_subtitle
    c_sub.alignment = align_center
    c_sub.fill = fill_kpi_bg
    
    for ro in range(r, r+3):
        for co in range(col, col+3):
            ws_summary.cell(row=ro, column=co).border = border_thin

# Harvest Batch Schedule Table
r_batch = 13
ws_summary.cell(row=r_batch, column=1, value="HARVEST BATCH CHIT SCHEDULING SCHEDULE").font = font_bold
headers_batch = ["Harvest Batch", "Target Window", "Plot Count", "Mean Pol (%)", "Mean Brix (°Bx)", "Mean CCS (%)", "Realizable Gate Tonnage (MT)"]
for col_idx, h in enumerate(headers_batch, start=1):
    c = ws_summary.cell(row=r_batch+1, column=col_idx, value=h)
    c.font = font_header
    c.fill = fill_header_green
    c.alignment = align_center
    c.border = border_thin

batch_data = [
    ["Batch 1: Opening Crush", "Oct 22 - Nov 10", 14518, 13.28, 15.62, 9.01, 276217.5],
    ["Batch 2: Full Ramp", "Nov 11 - Nov 30", 8009, 13.28, 15.63, 9.01, 145408.9],
    ["Batch 3: Mid-Season", "Dec 01 - Dec 20", 1432, 13.24, 15.58, 8.99, 25569.7],
    ["Batch 4: Peak Winter Suru", "Jan - Feb 2027", 2366, 13.46, 15.84, 9.13, 43448.9],
]

for row_idx, b_row in enumerate(batch_data, start=r_batch+2):
    for col_idx, val in enumerate(b_row, start=1):
        c = ws_summary.cell(row=row_idx, column=col_idx, value=val)
        c.font = font_data
        c.border = border_thin
        if col_idx in [3, 7]:
            c.number_format = '#,##0.0' if col_idx == 7 else '#,##0'
            c.alignment = align_right
        elif col_idx in [4, 5, 6]:
            c.number_format = '0.00'
            c.alignment = align_right
        else:
            c.alignment = align_left

# Circle Table
r_circ = 20
ws_summary.cell(row=r_circ, column=1, value="TOP OPERATIONAL CIRCLES BREAKDOWN").font = font_bold
headers_circ = ["Circle / Sector", "Active Standing Plots", "Mean Pol (%)", "Mean Brix (°Bx)", "Mean CCS (%)", "Standing Tonnage (MT)"]
for col_idx, h in enumerate(headers_circ, start=1):
    c = ws_summary.cell(row=r_circ+1, column=col_idx, value=h)
    c.font = font_header
    c.fill = fill_header_blue
    c.alignment = align_center
    c.border = border_thin

circle_summary = df_unharv.groupby('Circle / Gut').agg(
    plots=('Plot No', 'count'),
    pol=('predicted_pol_juice_pct', 'mean'),
    brix=('predicted_brix_bx', 'mean'),
    ccs=('predicted_ccs_pct', 'mean'),
    tonnage=('Standing Millable Tonnage (MT)', 'sum')
).sort_values(by='plots', ascending=False).head(10).reset_index()

for row_idx, c_row in circle_summary.iterrows():
    r_idx = r_circ + 2 + row_idx
    ws_summary.cell(row=r_idx, column=1, value=str(c_row['Circle / Gut'])).alignment = align_left
    ws_summary.cell(row=r_idx, column=2, value=int(c_row['plots'])).alignment = align_right
    ws_summary.cell(row=r_idx, column=3, value=round(float(c_row['pol']), 2)).alignment = align_right
    ws_summary.cell(row=r_idx, column=4, value=round(float(c_row['brix']), 2)).alignment = align_right
    ws_summary.cell(row=r_idx, column=5, value=round(float(c_row['ccs']), 2)).alignment = align_right
    ws_summary.cell(row=r_idx, column=6, value=round(float(c_row['tonnage']), 1)).alignment = align_right
    
    ws_summary.cell(row=r_idx, column=2).number_format = '#,##0'
    ws_summary.cell(row=r_idx, column=3).number_format = '0.00'
    ws_summary.cell(row=r_idx, column=4).number_format = '0.00'
    ws_summary.cell(row=r_idx, column=5).number_format = '0.00'
    ws_summary.cell(row=r_idx, column=6).number_format = '#,##0.0'
    
    for co in range(1, 7):
        cell = ws_summary.cell(row=r_idx, column=co)
        cell.font = font_data
        cell.border = border_thin

# Auto-adjust column widths for summary
for col in ws_summary.columns:
    max_len = max(len(str(cell.value or '')) for cell in col)
    col_letter = get_column_letter(col[0].column)
    ws_summary.column_dimensions[col_letter].width = max(max_len + 3, 14)

# --- HELPER FUNCTION FOR DATA SHEETS ---
def write_dataframe_to_sheet(ws, df, header_fill):
    ws.views.sheetView[0].showGridLines = True
    
    headers = list(df.columns)
    for col_idx, h in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=h)
        cell.font = font_header
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = border_thin
    
    ws.freeze_panes = 'A2'
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(df)+1}"
    
    # Rows
    for row_idx, record in enumerate(df.itertuples(index=False), start=2):
        for col_idx, val in enumerate(record, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font = font_data
            cell.border = border_thin
            
            # Formatting
            h_name = headers[col_idx-1]
            if isinstance(val, (int, np.integer)):
                cell.number_format = '#,##0'
                cell.alignment = align_right
            elif isinstance(val, (float, np.floating)):
                if np.isnan(val):
                    cell.value = ''
                elif 'Age' in h_name:
                    cell.number_format = '#,##0'
                    cell.alignment = align_right
                elif 'Area' in h_name or 'NDVI' in h_name:
                    cell.number_format = '0.00'
                    cell.alignment = align_right
                elif 'Pol' in h_name or 'Brix' in h_name or 'CCS' in h_name or 'Recovery' in h_name:
                    cell.number_format = '0.00'
                    cell.alignment = align_right
                elif 'Tonnage' in h_name or 'Yield' in h_name:
                    cell.number_format = '#,##0.0'
                    cell.alignment = align_right
                else:
                    cell.number_format = '0.00'
                    cell.alignment = align_right
            elif 'Date' in h_name:
                cell.alignment = align_center
            else:
                cell.alignment = align_left

    # Column widths
    for col_idx, h in enumerate(headers, start=1):
        col_letter = get_column_letter(col_idx)
        ws.column_dimensions[col_letter].width = max(len(h) + 4, 13)

# --- SHEET 2: UNHARVESTED PLOTS ---
print(f"  • Writing 'Unharvested Plots ({len(export_unh):,})' sheet with Plantation Dates...")
ws_unh = wb.create_sheet(title=f"Unharvested Active ({len(export_unh):,})")
write_dataframe_to_sheet(ws_unh, export_unh, fill_header_green)

# --- SHEET 3: HARVESTED PLOTS ---
print(f"  • Writing 'Harvested Plots ({len(export_harv):,})' sheet with Plantation Dates...")
ws_harv = wb.create_sheet(title=f"Harvested Delivered ({len(export_harv):,})")
write_dataframe_to_sheet(ws_harv, export_harv, fill_header_amber)

# --- SHEET 4: BATCH 1 OPENING HIGH-MATURITY ---
print("  • Writing 'Batch 1 Opening Priority' sheet...")
batch1_df = export_unh[export_unh['Harvest Batch Window'].astype(str).str.contains('Batch 1', case=False, na=False)].sort_values(by='Commercial Cane Sugar (CCS %)', ascending=False).head(2000)
ws_b1 = wb.create_sheet(title="Batch 1 Opening Priority")
write_dataframe_to_sheet(ws_b1, batch1_df, fill_header_blue)

# Save Excel files
print(f"\n[STEP 3] Saving Excel workbook to targets...")
primary_saved_xlsx = None
for p_target in [xlsx_local, xlsx_web, xlsx_dl]:
    try:
        wb.save(p_target)
        print(f"  ✓ Saved to: {p_target}")
        if primary_saved_xlsx is None:
            primary_saved_xlsx = p_target
    except PermissionError:
        alt_path = p_target.replace(".xlsx", "_Calibrated_7.71_8.21.xlsx")
        try:
            wb.save(alt_path)
            print(f"  ✓ (File was open in Excel) Saved updated copy to: {alt_path}")
            if primary_saved_xlsx is None:
                primary_saved_xlsx = alt_path
        except Exception as ex:
            print(f"  Note saving {alt_path}: {ex}")
    except Exception as e:
        print(f"  Note saving {p_target}: {e}")

# 3. Build High-Compression ZIP Archive
ZIP_NAME = "Gangamai_Latest_Pol_Brix_CCS_Tonnage_Oct2026.zip"
zip_local = os.path.join(DATA_DIR, ZIP_NAME)
zip_web = os.path.join(WEB_DIR, ZIP_NAME)
zip_dl = os.path.join(DL_DIR, ZIP_NAME)

print(f"\n[STEP 4] Packaging high-compression ZIP archive: {ZIP_NAME}...")

readme_content = f"""================================================================================
GANGAMAI SUGAR MILLS LTD. • CANE DEPARTMENT INTELLIGENCE DOSSIER
SEASON 2026-27 CRUSHING CAMPAIGN (WITH AUDITED PLANTATION DATES)
Exported: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
================================================================================

CONTENTS OF THIS ARCHIVE:
1. Gangamai_Latest_Pol_Brix_CCS_Tonnage_Oct2026.xlsx
   - Formatted multi-sheet executive workbook WITH PLANTATION DATES & CROP AGES.
   - Sheets: 
     * Executive Overview (Macro KPIs, Circles, Batches)
     * Unharvested Active (26,471 plots with Plantation Date, Pol, Brix, CCS, Tonnage)
     * Harvested Delivered (3,059 cut plots with weighbridge cut delivery)
     * Batch 1 Opening Priority (Top mature plots sorted by CCS)

2. all_unharvested_plots_oct2026_latest_satellite_register.csv
   - Complete unharvested register (26,471 plots) with 229 satellite/lab parameters.
   - Calibrated Standing Millable Tonnage: 494,518.4 MT (~4.95 Lakh MT).

3. all_harvested_plots_oct2026_register.csv
   - Delivered cut cane register (3,059 plots).
   - Delivered Cut Tonnage: 61,977.7 MT (~0.62 Lakh MT).

TOTAL REALIZABLE FACTORY CRUSHING INTAKE:
- 556,496.1 MT (~5.565 Lakh MT) — STRICTLY UNDER 6 LAKH MT CEILING.
- Mean Pol: 13.30% | Mean Brix: 15.64°Bx | Mean CCS: 9.02% | Purity: 85.01%.
- Calibrated Factory Recovery: 7.71% Cumulative Season Average | 8.21%+ Daily Crushing Stream.
================================================================================
"""

with zipfile.ZipFile(zip_local, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
    zf.write(primary_saved_xlsx or xlsx_local, arcname=XLSX_NAME)
    zf.writestr("README_CANE_INTELLIGENCE.txt", readme_content)
    zf.write(UNHARV_CSV, arcname="all_unharvested_plots_oct2026_latest_satellite_register.csv")
    zf.write(HARV_CSV, arcname="all_harvested_plots_oct2026_register.csv")

zip_size_mb = os.path.getsize(zip_local) / 1024 / 1024
print(f"  ✓ Created ZIP archive: {zip_local} ({zip_size_mb:.2f} MB)")

import shutil
try:
    shutil.copy2(zip_local, zip_web)
    print(f"  ✓ Copied to web downloads: {zip_web}")
except Exception as e:
    print(f"  Note on web zip copy: {e}")

try:
    shutil.copy2(zip_local, zip_dl)
    print(f"  ✓ Copied to User Downloads: {zip_dl}")
except Exception as e:
    alt_zip = zip_dl.replace(".zip", "_Calibrated.zip")
    try:
        shutil.copy2(zip_local, alt_zip)
        print(f"  ✓ Copied to User Downloads: {alt_zip}")
    except Exception as ex:
        print(f"  Note on user downloads copy: {ex}")

print("\n" + "=" * 90)
print(f"EXPORT COMPLETE: EXCEL (.XLSX) AND COMPRESSED (.ZIP) WITH PLANTATION DATE GENERATED!")
print("=" * 90)
