import csv
import json
import time
import argparse
import urllib.request
import urllib.parse
from datetime import datetime

"""
Satellite Data CSV Linker & Enricher Script
===========================================
This script reads an input CSV file containing latitude, longitude, and optional date columns,
queries Satellite / Earth Observation APIs (NASA POWER API, Open-Meteo Satellite API),
and exports an enriched CSV with satellite metrics appended.

No external dependencies required (uses built-in Python modules: csv, json, urllib).
"""

def detect_coordinate_columns(header):
    lat_col = None
    lon_col = None
    date_col = None

    for col in header:
        clean = col.strip().lower()
        if clean in ['lat', 'latitude', 'y', 'lat_deg', 'lat_dd']:
            lat_col = col
        elif clean in ['lon', 'long', 'longitude', 'x', 'lon_deg', 'lng', 'lon_dd']:
            lon_col = col
        elif clean in ['date', 'time', 'timestamp', 'datetime', 'day']:
            date_col = col

    return lat_col, lon_col, date_col

def fetch_nasa_power_data(lat, lon, start_date=None, end_date=None):
    """
    Fetches Satellite Meteorological and Solar Radiation Data from NASA POWER API.
    FREE & No API Key required.
    Parameters fetched:
      - T2M: Temperature at 2 Meters (deg C)
      - ALLSKY_SFC_SW_DWN: All-Sky Surface Shortwave Irradiance (kW-hr/m^2/day)
      - PRECTOTCORR: Corrected Total Precipitation (mm/day)
      - RH2M: Relative Humidity at 2 Meters (%)
      - WS10M: Wind Speed at 10 Meters (m/s)
      - CLOUD_AMT: Daylight Cloud Amount (%)
    """
    if not start_date:
        start_date = "20240101"
    else:
        start_date = start_date.replace('-', '').replace('/', '')[:8]
    if not end_date:
        end_date = start_date

    url = (
        f"https://power.larc.nasa.gov/api/temporal/daily/point?"
        f"parameters=T2M,ALLSKY_SFC_SW_DWN,PRECTOTCORR,RH2M,WS10M,CLOUD_AMT&"
        f"community=RE&longitude={lon}&latitude={lat}&"
        f"start={start_date}&end={end_date}&format=JSON"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SatelliteCSVLinker/1.0'})
        with urllib.request.urlopen(req, timeout=12) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                params = data.get('properties', {}).get('parameter', {})
                
                t2m_dict = params.get('T2M', {})
                first_key = next(iter(t2m_dict.keys()), None) if t2m_dict else None
                
                if first_key:
                    return {
                        'sat_temp_celsius': t2m_dict.get(first_key, 'N/A'),
                        'sat_solar_radiation_kwh_m2': params.get('ALLSKY_SFC_SW_DWN', {}).get(first_key, 'N/A'),
                        'sat_precipitation_mm': params.get('PRECTOTCORR', {}).get(first_key, 'N/A'),
                        'sat_humidity_pct': params.get('RH2M', {}).get(first_key, 'N/A'),
                        'sat_wind_speed_ms': params.get('WS10M', {}).get(first_key, 'N/A'),
                        'sat_cloud_cover_pct': params.get('CLOUD_AMT', {}).get(first_key, 'N/A'),
                        'satellite_source': 'NASA_POWER_SATELLITE'
                    }
    except Exception as e:
        print(f"  [Warning] NASA POWER API error for ({lat}, {lon}): {e}")

    return {
        'sat_temp_celsius': 'N/A',
        'sat_solar_radiation_kwh_m2': 'N/A',
        'sat_precipitation_mm': 'N/A',
        'sat_humidity_pct': 'N/A',
        'sat_wind_speed_ms': 'N/A',
        'sat_cloud_cover_pct': 'N/A',
        'satellite_source': 'ERROR_OR_TIMEOUT'
    }

def fetch_open_meteo_satellite_data(lat, lon, date_str=None):
    """
    Fetches Satellite & Historical Reanalysis Weather from Open-Meteo API.
    FREE & No API Key required.
    """
    if not date_str:
        date_str = "2024-06-01"
    else:
        date_str = date_str[:10]

    url = (
        f"https://archive-api.open-meteo.com/v1/archive?"
        f"latitude={lat}&longitude={lon}&start_date={date_str}&end_date={date_str}&"
        f"daily=temperature_2m_mean,precipitation_sum,shortwave_radiation_sum,relative_humidity_2m_mean,wind_speed_10m_max&"
        f"timezone=auto"
    )

    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'SatelliteCSVLinker/1.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                daily = data.get('daily', {})
                
                temps = daily.get('temperature_2m_mean', [None])
                precip = daily.get('precipitation_sum', [None])
                solar = daily.get('shortwave_radiation_sum', [None])
                rh = daily.get('relative_humidity_2m_mean', [None])
                wind = daily.get('wind_speed_10m_max', [None])

                solar_kwh = round(solar[0] * 0.277778, 2) if solar and solar[0] is not None else 'N/A'

                return {
                    'sat_temp_celsius': temps[0] if temps and temps[0] is not None else 'N/A',
                    'sat_solar_radiation_kwh_m2': solar_kwh,
                    'sat_precipitation_mm': precip[0] if precip and precip[0] is not None else 'N/A',
                    'sat_humidity_pct': rh[0] if rh and rh[0] is not None else 'N/A',
                    'sat_wind_speed_ms': wind[0] if wind and wind[0] is not None else 'N/A',
                    'sat_cloud_cover_pct': 'N/A',
                    'satellite_source': 'OPEN_METEO_SATELLITE'
                }
    except Exception as e:
        print(f"  [Warning] Open-Meteo API error for ({lat}, {lon}): {e}")

    return fetch_nasa_power_data(lat, lon, date_str)

def process_csv(input_path, output_path, api_provider='nasa'):
    print(f"==================================================")
    print(f"Satellite Data CSV Linker - Processing File")
    print(f"Input File : {input_path}")
    print(f"Output File: {output_path}")
    print(f"API Engine : {api_provider.upper()}")
    print(f"==================================================")

    with open(input_path, mode='r', encoding='utf-8-sig') as infile:
        reader = csv.DictReader(infile)
        fieldnames = list(reader.fieldnames)

        lat_col, lon_col, date_col = detect_coordinate_columns(fieldnames)

        if not lat_col or not lon_col:
            print("[Error] Could not automatically identify Latitude and Longitude columns!")
            print(f"Detected columns: {fieldnames}")
            print("Please ensure your CSV has column headers like 'latitude' / 'lat' and 'longitude' / 'lon'.")
            return

        print(f"[Info] Found coordinate columns: Latitude='{lat_col}', Longitude='{lon_col}', Date='{date_col}'")

        new_cols = [
            'sat_temp_celsius',
            'sat_solar_radiation_kwh_m2',
            'sat_precipitation_mm',
            'sat_humidity_pct',
            'sat_wind_speed_ms',
            'sat_cloud_cover_pct',
            'satellite_source'
        ]
        
        output_fieldnames = fieldnames + [col for col in new_cols if col not in fieldnames]

        rows = list(reader)
        total_rows = len(rows)
        print(f"[Info] Found {total_rows} locations to link with Satellite Data API...\n")

        enriched_rows = []
        for index, row in enumerate(rows, start=1):
            try:
                lat = float(row[lat_col])
                lon = float(row[lon_col])
            except (ValueError, TypeError):
                print(f"  Row {index}: Invalid lat/lon values. Skipping satellite fetch.")
                row.update({col: 'N/A' for col in new_cols})
                enriched_rows.append(row)
                continue

            date_val = row.get(date_col) if date_col else None
            print(f" -> Fetching satellite data for Row {index}/{total_rows}: Lat {lat:.4f}, Lon {lon:.4f}...", end="", flush=True)

            if api_provider.lower() == 'open-meteo':
                sat_data = fetch_open_meteo_satellite_data(lat, lon, date_val)
            else:
                sat_data = fetch_nasa_power_data(lat, lon, date_val)

            print(f" Done! (Temp: {sat_data.get('sat_temp_celsius')} deg C, Solar: {sat_data.get('sat_solar_radiation_kwh_m2')} kWh/m2)")
            
            row.update(sat_data)
            enriched_rows.append(row)

            time.sleep(0.2)

    with open(output_path, mode='w', newline='', encoding='utf-8') as outfile:
        writer = csv.DictWriter(outfile, fieldnames=output_fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"\n==================================================")
    print(f"Success! Enriched satellite CSV saved to: {output_path}")
    print(f"==================================================")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Link CSV location data with Satellite Data APIs (NASA POWER / Open-Meteo).")
    parser.add_argument("-i", "--input", default="sample_locations.csv", help="Input CSV file path")
    parser.add_argument("-o", "--output", default="enriched_satellite_output.csv", help="Output CSV file path")
    parser.add_argument("-a", "--api", choices=['nasa', 'open-meteo'], default="nasa", help="Satellite API Provider")

    args = parser.parse_args()
    process_csv(args.input, args.output, args.api)
