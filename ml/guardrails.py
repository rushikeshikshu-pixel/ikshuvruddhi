# -*- coding: utf-8 -*-
"""
ml/guardrails.py
================
Permanent Algorithmic Guardrails for SatCane AI Engine:
1. Guardrail 1: Satellite Emergence Age Harmonizer (Overrides false/late survey dates)
2. Guardrail 2: Soil-Moderated Drainage Gate (Prevents false waterlogging penalties on permeable soils)
3. Guardrail 3: Stunted Ratoon Degradation Cap (Caps stunted Khodwa at <= 14.35 Bx / 12.10 Pol)
4. Guardrail 4: Coupled Cut-to-Crush Transit Invertase Staling Kinetics
"""

import numpy as np
import pandas as pd

def apply_satellite_emergence_age_harmonizer(df):
    """
    Guardrail 1:
    If a plot exhibits high vegetative canopy vigor (NDVI >= 0.65, NDRE >= 0.45)
    and structural stalk volume, but recorded age is < 350 days, the survey date
    was booked late. Harmonizes effective age up to true biological emergence.
    """
    df = df.copy()
    if 'crop_age_days' in df.columns:
        ages = pd.to_numeric(df['crop_age_days'], errors='coerce').fillna(330.0).values
        ndvis = pd.to_numeric(df.get('optical_ndvi', 0.60), errors='coerce').fillna(0.60).values
        ndres = pd.to_numeric(df.get('optical_ndre', 0.40), errors='coerce').fillna(0.40).values
        
        mask = (ndvis >= 0.65) & (ndres >= 0.45) & (ages < 350.0)
        harmonized_ages = ages.copy()
        harmonized_ages[mask] = np.minimum(410.0, ages[mask] + 55.0 * ((ndvis[mask] - 0.60) / 0.15))
        df['crop_age_days'] = harmonized_ages
    return df

def apply_soil_moderated_drainage_gate(df):
    """
    Guardrail 2:
    High Topographic Wetness Index (TWI > 9.5) only causes root waterlogging if
    the soil has high vertisol clay and flat slope (< 0.8%).
    If soil is permeable sandy-loam (sand/clay > 0.60 and slope >= 0.70%),
    drainage is rapid and artificial waterlogging penalties are neutralized.
    """
    df = df.copy()
    if 'topographic_wetness_index' in df.columns:
        twis = pd.to_numeric(df['topographic_wetness_index'], errors='coerce').fillna(9.0).values
        slopes = pd.to_numeric(df.get('dem_slope_pct', 1.0), errors='coerce').fillna(1.0).values
        clays = pd.to_numeric(df.get('clay_pct', 35.0), errors='coerce').fillna(35.0).values
        sands = pd.to_numeric(df.get('sand_pct', 25.0), errors='coerce').fillna(25.0).values
        
        permeability = sands / np.maximum(clays, 10.0)
        well_drained_mask = (permeability > 0.60) & (slopes >= 0.70)
        
        adjusted_twis = twis.copy()
        adjusted_twis[well_drained_mask] = np.minimum(twis[well_drained_mask], 7.50)
        df['topographic_wetness_index'] = adjusted_twis
    return df

def apply_stunted_ratoon_degradation_cap(df, pred_brix, pred_pol):
    """
    Guardrail 3:
    If a ratoon (Khodwa) is recorded at > 300 days but exhibits severe standing canopy deficit
    (0.42 <= NDVI < 0.62 and LSWI < 0.18), root-grub / moisture failure shuts down sucrose synthesis.
    Caps predicted sugar to reflect stunted biological reality.
    Note: If NDVI < 0.42 and previous canopy was high (>= 0.65), the plot was partially harvested
    rather than stunted, so standing mature cane values are preserved.
    """
    pred_brix = np.array(pred_brix, dtype=float)
    pred_pol = np.array(pred_pol, dtype=float)
    
    cane_types = df.get('Cane Type', pd.Series(['Suru'] * len(df))).astype(str).values
    ndvis = pd.to_numeric(df.get('optical_ndvi', 0.60), errors='coerce').fillna(0.60).values
    lswis = pd.to_numeric(df.get('optical_lswi', 0.20), errors='coerce').fillna(0.20).values
    prev_ndvis = pd.to_numeric(df.get('previous_optical_ndvi', 0.60), errors='coerce').fillna(0.60).values
    cut_tons = pd.to_numeric(df.get('Harvested Cut Tonnage (MT)', 0.0), errors='coerce').fillna(0.0).values
    
    # Stunted standing khodwa has active low-vigor canopy, NOT freshly harvested stubble
    is_khodwa = np.array(['Khodwa' in str(ct) for ct in cane_types])
    is_cut_or_harvested = (ndvis < 0.42) & ((prev_ndvis >= 0.65) | (cut_tons > 0.0))
    is_stunted_khodwa = is_khodwa & (ndvis >= 0.42) & (ndvis < 0.62) & (lswis < 0.18) & (~is_cut_or_harvested)
    
    pred_brix[is_stunted_khodwa] = np.minimum(pred_brix[is_stunted_khodwa], 14.35)
    pred_pol[is_stunted_khodwa] = np.minimum(pred_pol[is_stunted_khodwa], 12.10)
    
    return pred_brix, pred_pol

def compute_cut_to_crush_delivered_sucrose(pred_standing_brix, pred_standing_pol, distance_km, transit_hours=None, ambient_temp_c=32.0):
    """
    Guardrail 4:
    Coupled cut-to-crush transit loss physics:
    - Invertase enzyme kinetics degrade Pol % based on transit time and temperature
    - Transpiration and sunlight exposure concentrate juice, increasing Brix %
    """
    dist = np.array(distance_km, dtype=float)
    if transit_hours is None:
        hours = 8.0 + (dist * 0.16)  # Base queue (8h) + tractor speed (6.25 km/h)
    else:
        hours = np.array(transit_hours, dtype=float)
        
    temp_factor = np.exp((ambient_temp_c - 28.0) / 18.0)
    inversion_loss_pol = hours * 0.038 * temp_factor
    evaporation_gain_brix = np.where(hours > 12.0, (hours - 12.0) * 0.022, 0.0)
    
    delivered_pol = np.array(pred_standing_pol, dtype=float) - inversion_loss_pol
    delivered_brix = np.array(pred_standing_brix, dtype=float) + evaporation_gain_brix
    
    # Enforce minimum purity bounds
    delivered_brix = np.maximum(delivered_brix, delivered_pol + 1.10)
    
    return delivered_brix, delivered_pol, inversion_loss_pol, hours
