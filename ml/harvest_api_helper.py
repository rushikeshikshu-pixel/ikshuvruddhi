import os
import json
import math
import re

_CALIBRATED_PLOTS_CACHE = None
# Same wording the console already prints below the payment-confidence line.
PLANNING_STAMP = "PLANNING ONLY — NOT VALID FOR PAYMENT"

_DEFAULT_HARVEST_CONFIG = {
    "eligibility_mode": "relative",
    "ccs_percentile": 50.0,
    "absolute_min_ccs": 11.2,
    "mill_lat": None,
    "mill_lon": None,
    "mill_coordinates_verified": False,
}

def get_calibrated_plots_list():
    global _CALIBRATED_PLOTS_CACHE
    if _CALIBRATED_PLOTS_CACHE is not None:
        return _CALIBRATED_PLOTS_CACHE
    
    base_dir = os.path.dirname(os.path.dirname(__file__))
    plots_file = os.path.join(base_dir, "web", "mill_calibrated_plots.js")
    if not os.path.exists(plots_file):
        return []
    try:
        with open(plots_file, "r", encoding="utf-8") as f:
            c = f.read()
        m = re.search(r'\[.*\]', c, re.DOTALL)
        if m:
            _CALIBRATED_PLOTS_CACHE = json.loads(m.group(0))
            return _CALIBRATED_PLOTS_CACHE
    except Exception as exc:
        print(f"[IkshuVruddhi] Warning: failed loading calibrated plots: {exc}")
    return []


def _float_or_none(value):
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _ccs_or_zero(plot):
    # Same fallback the original cutoff used: a missing CCS does not pass.
    value = _float_or_none(plot.get("ccs")) if isinstance(plot, dict) else None
    return 0.0 if value is None else value


def load_harvest_config():
    """Season settings. Env overrides the file; arguments override both."""
    cfg = dict(_DEFAULT_HARVEST_CONFIG)
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "harvest.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                loaded = json.load(handle)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except Exception as exc:
            print(f"[IkshuVruddhi] Warning: failed loading harvest config: {exc}")

    mode = os.getenv("IKSHU_ELIGIBILITY_MODE")
    if mode:
        cfg["eligibility_mode"] = mode.strip().lower()
    percentile = os.getenv("IKSHU_CCS_PERCENTILE")
    if _float_or_none(percentile) is not None:
        cfg["ccs_percentile"] = _float_or_none(percentile)
    absolute = os.getenv("IKSHU_MIN_CCS")
    if _float_or_none(absolute) is not None:
        cfg["absolute_min_ccs"] = _float_or_none(absolute)
    lat = os.getenv("IKSHU_MILL_LAT")
    lon = os.getenv("IKSHU_MILL_LON")
    if _float_or_none(lat) is not None:
        cfg["mill_lat"] = _float_or_none(lat)
    if _float_or_none(lon) is not None:
        cfg["mill_lon"] = _float_or_none(lon)
    verified = os.getenv("IKSHU_MILL_COORDS_VERIFIED")
    if verified not in (None, ""):
        cfg["mill_coordinates_verified"] = verified.strip().lower() in ("1", "true", "yes", "y")
    return cfg


def _normalize_mode(mode):
    if mode is None or str(mode).strip() == "":
        return None
    name = str(mode).strip().lower()
    if name in ("relative", "percentile", "season"):
        return "relative"
    if name in ("absolute", "fixed", "cutoff"):
        return "absolute"
    return "relative"


def resolve_queue_settings(eligibility_mode=None, min_ccs=None, ccs_percentile=None):
    cfg = load_harvest_config()
    mode = _normalize_mode(eligibility_mode) or _normalize_mode(cfg.get("eligibility_mode")) or "relative"
    resolved_min = min_ccs if min_ccs is not None else cfg.get("absolute_min_ccs", 11.2)
    resolved_min = _float_or_none(resolved_min)
    if resolved_min is None:
        resolved_min = 11.2
    resolved_pct = ccs_percentile if ccs_percentile is not None else cfg.get("ccs_percentile", 50.0)
    resolved_pct = _float_or_none(resolved_pct)
    if resolved_pct is None:
        resolved_pct = 50.0
    resolved_pct = min(100.0, max(0.0, resolved_pct))
    return {
        "mode": mode,
        "min_ccs": resolved_min,
        "ccs_percentile": resolved_pct,
        "mill": resolve_mill_point(cfg),
    }


def percentile_linear(values, pct):
    """Linear percentile of the current-season CCS list. pct is 0-100."""
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    pct = min(100.0, max(0.0, float(pct)))
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * (pct / 100.0)
    lo = int(math.floor(k))
    hi = min(lo + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def season_ccs_percentile(ccs, values):
    if ccs is None or not values:
        return None
    return round(100.0 * sum(1 for value in values if value <= ccs) / len(values), 1)


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle kilometres. Road distance is intentionally not applied here."""
    radius = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lam = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lam / 2.0) ** 2
    return 2.0 * radius * math.asin(min(1.0, math.sqrt(a)))


def plot_lat_lon(plot):
    if not isinstance(plot, dict):
        return None
    lat = _float_or_none(plot.get("lat", plot.get("latitude")))
    lon = _float_or_none(plot.get("lon", plot.get("longitude", plot.get("lng"))))
    if lat is not None and lon is not None:
        return lat, lon
    centroid = plot.get("centroid")
    if isinstance(centroid, dict):
        lat = _float_or_none(centroid.get("lat", centroid.get("latitude")))
        lon = _float_or_none(centroid.get("lon", centroid.get("longitude", centroid.get("lng"))))
        if lat is not None and lon is not None:
            return lat, lon
    return None


def resolve_mill_point(cfg=None):
    cfg = cfg or load_harvest_config()
    lat = _float_or_none(cfg.get("mill_lat"))
    lon = _float_or_none(cfg.get("mill_lon"))
    if lat is None or lon is None:
        return None
    return {
        "lat": lat,
        "lon": lon,
        "verified": bool(cfg.get("mill_coordinates_verified")),
    }


def resolve_plot_distance(plot, mill=None):
    """
    Kilometres from the plot to the mill.
    A future road router can set roadDistanceKm; until then haversine is used.
    """
    # TODO: when a road-network feed is connected, prefer that distance and keep
    # haversine as the fallback. Do not invent a tortuosity factor here.
    road = None
    if isinstance(plot, dict):
        road = _float_or_none(plot.get("roadDistanceKm"))
        if road is None:
            road = _float_or_none(plot.get("road_distance_km"))
    if road is not None:
        return road, {"method": "road", "source_tag": "D", "mill_point_source_tag": None}

    coords = plot_lat_lon(plot)
    if mill is not None and coords is not None:
        km = round(haversine_km(coords[0], coords[1], mill["lat"], mill["lon"]), 2)
        return km, {
            "method": "haversine",
            "source_tag": "D",
            "mill_point_source_tag": "M" if mill.get("verified") else "?",
        }

    stored = None
    if isinstance(plot, dict):
        stored = _float_or_none(plot.get("distKm"))
        if stored is None:
            stored = _float_or_none(plot.get("distance_km"))
    if stored is None:
        return None, {"method": None, "source_tag": "?", "mill_point_source_tag": "?"}
    return stored, {"method": "register", "source_tag": "?", "mill_point_source_tag": None}


def _planning_stamp(mode, mill):
    verified = bool(mill and mill.get("verified"))
    if mode == "relative" or not verified:
        return PLANNING_STAMP
    return None


def _transit_hours_and_loss(distance_km, ambient_temp_c=32.0):
    """Same default path as compute_cut_to_crush_delivered_sucrose."""
    hours = 8.0 + (float(distance_km) * 0.16)
    temp_factor = math.exp((ambient_temp_c - 28.0) / 18.0)
    return hours, hours * 0.038 * temp_factor


_TRANSIT_FN = {"ready": False, "fn": None}


def _cut_to_crush_fn():
    if not _TRANSIT_FN["ready"]:
        _TRANSIT_FN["ready"] = True
        try:
            from ml.guardrails import compute_cut_to_crush_delivered_sucrose
            _TRANSIT_FN["fn"] = compute_cut_to_crush_delivered_sucrose
        except Exception:
            _TRANSIT_FN["fn"] = None
    return _TRANSIT_FN["fn"]


def _travel_from_distance(plot, distance_km):
    """Feed this plot's kilometres into the cut-to-crush transit model."""
    if distance_km is None:
        return None
    hours, loss = _transit_hours_and_loss(distance_km)
    brix = _float_or_none(plot.get("brix")) if isinstance(plot, dict) else None
    pol = _float_or_none(plot.get("pol")) if isinstance(plot, dict) else None
    transit = _cut_to_crush_fn()
    if transit is not None and brix is not None and pol is not None:
        _brix, _pol, loss, hours = transit(brix, pol, distance_km)
        hours, loss = float(hours), float(loss)
    return {
        "distance_km": distance_km,
        "estimated_transit_hours": round(float(hours), 2),
        "estimated_inversion_loss_pol": round(float(loss), 3),
    }


def build_plot_trajectory(p: dict) -> list:
    curr_ccs = float(p.get("ccs", 11.2))
    curr_brix = float(p.get("brix", 19.5))
    curr_pol = float(p.get("pol", 15.0))
    curr_ndvi = float(p.get("ndvi", 0.70))
    
    passes = [
        {"pass": 15, "date": "2026-09-20", "ndvi": round(curr_ndvi * 0.84, 2), "brix": round(max(curr_brix - 2.8, 14.0), 1), "pol": round(max(curr_pol - 2.6, 10.5), 1), "ccs": round(max(curr_ccs - 2.4, 8.5), 1), "status": "VEGETATIVE"},
        {"pass": 16, "date": "2026-09-25", "ndvi": round(curr_ndvi * 0.89, 2), "brix": round(max(curr_brix - 2.0, 15.5), 1), "pol": round(max(curr_pol - 1.9, 11.8), 1), "ccs": round(max(curr_ccs - 1.8, 9.5), 1), "status": "VEGETATIVE"},
        {"pass": 17, "date": "2026-09-30", "ndvi": round(curr_ndvi * 0.94, 2), "brix": round(max(curr_brix - 1.3, 16.8), 1), "pol": round(max(curr_pol - 1.2, 13.0), 1), "ccs": round(max(curr_ccs - 1.1, 10.4), 1), "status": "WINDOW_15D"},
        {"pass": 18, "date": "2026-10-05", "ndvi": round(curr_ndvi * 0.98, 2), "brix": round(max(curr_brix - 0.6, 18.0), 1), "pol": round(max(curr_pol - 0.5, 14.2), 1), "ccs": round(max(curr_ccs - 0.5, 11.0), 1), "status": "WINDOW_15D" if curr_ccs < 11.7 else "CUT_NOW"},
        {"pass": 19, "date": "2026-10-10", "ndvi": round(curr_ndvi, 2), "brix": round(curr_brix, 1), "pol": round(curr_pol, 1), "ccs": round(curr_ccs, 1), "status": p.get("status", "CUT_NOW")}
    ]
    return passes

def calculate_cutting_queue(
    circle: str = "ALL",
    min_ccs: float = None,
    target_mt: float = 4500.0,
    delta_only: bool = False,
    pass_date: str = "2026-10-10",
    eligibility_mode: str = None,
    ccs_percentile: float = None,
) -> dict:
    all_plots = get_calibrated_plots_list()
    if not all_plots:
        return {"status": "ERROR", "message": "Calibrated plot register unavailable."}

    settings = resolve_queue_settings(eligibility_mode, min_ccs, ccs_percentile)
    mode = settings["mode"]
    absolute_min = settings["min_ccs"]
    percentile = settings["ccs_percentile"]
    mill = settings["mill"]

    plots = [p for p in all_plots if not p.get("isGhost", False)]
    if circle != "ALL":
        plots = [p for p in plots if p.get("circle", "").lower() == circle.lower()]

    season_ccs = [_ccs_or_zero(p) for p in plots]
    if mode == "absolute":
        threshold = float(absolute_min)
    else:
        threshold = percentile_linear(season_ccs, percentile)

    distance_of = {}
    distance_meta = {}
    for plot in plots:
        kilometres, meta = resolve_plot_distance(plot, mill)
        distance_of[id(plot)] = kilometres
        distance_meta[id(plot)] = meta

    if threshold is None:
        plots = []
    else:
        plots = [p for p in plots if _ccs_or_zero(p) + 1e-9 >= threshold]

    if delta_only and threshold is not None:
        plots = [
            p for p in plots
            if (_ccs_or_zero(p) - 0.5) < threshold <= _ccs_or_zero(p)
        ]

    plots.sort(key=lambda x: (-_ccs_or_zero(x), 99.0 if distance_of.get(id(x)) is None else distance_of[id(x)]))

    allocated = []
    accumulated_mt = 0.0
    for p in plots:
        tons = float(p.get("estTons", 30))
        if accumulated_mt + tons <= (target_mt * 1.10):
            allocated.append(p)
            accumulated_mt += tons
            if accumulated_mt >= target_mt:
                break

    if not allocated and plots:
        allocated = plots[:20]
        accumulated_mt = sum(float(p.get("estTons", 30)) for p in allocated)

    avg_ccs = round(sum(float(p.get("ccs", 0)) for p in allocated) / max(len(allocated), 1), 2)
    avg_brix = round(sum(float(p.get("brix", 0)) for p in allocated) / max(len(allocated), 1), 2)
    est_sugar_mt = round(accumulated_mt * (avg_ccs / 100.0), 1)

    distances = [distance_of.get(id(p)) for p in allocated if distance_of.get(id(p)) is not None]
    avg_distance = round(sum(distances) / len(distances), 2) if distances else None
    methods = {distance_meta.get(id(p), {}).get("method") for p in allocated}
    methods.discard(None)
    stamp = _planning_stamp(mode, mill)
    source_tag = "X" if mode == "relative" else "D"

    parcels = []
    for p in allocated:
        kilometres = distance_of.get(id(p))
        meta = distance_meta.get(id(p), {})
        travel = _travel_from_distance(p, kilometres)
        if travel is not None:
            travel["method"] = meta.get("method")
            travel["source_tag"] = meta.get("source_tag")
            travel["mill_point_source_tag"] = meta.get("mill_point_source_tag")
            if stamp:
                travel["planning_stamp"] = stamp
        parcels.append({
            "docket_id": p.get("docketId", f"DOK-{p.get('id')}"),
            "gat_no": p.get("gatNo"),
            "gat_number": p.get("gatNumber"),
            "farmer_en": p.get("farmerEn"),
            "farmer_mr": p.get("farmerMr"),
            "village": p.get("village"),
            "circle": p.get("circle"),
            "variety": p.get("variety"),
            "cane_type": p.get("caneType"),
            "reported_acres": p.get("repAcres"),
            "satellite_verified_acres": p.get("satAcres"),
            "est_tonnage_mt": p.get("estTons"),
            "predicted_ccs_pct": p.get("ccs"),
            "predicted_brix_deg": p.get("brix"),
            "predicted_pol_pct": p.get("pol"),
            "predicted_purity_pct": p.get("purity"),
            "season_ccs_percentile": season_ccs_percentile(_ccs_or_zero(p), season_ccs),
            "distance_km": kilometres,
            "distance_method": meta.get("method"),
            "distance_source_tag": meta.get("source_tag"),
            "mill_point_source_tag": meta.get("mill_point_source_tag"),
            "travel": travel,
            "max_transit_hours": p.get("transitTargetHours", 18),
            "harvest_window": "Optimal Next 7 Days"
        })

    return {
        "status": "SUCCESS",
        "api_protocol": "IKSHU-ERP-REST-V2",
        "satellite_pass": pass_date,
        "satellite_platform": "Sentinel-2A/B MSI L2A BOA",
        "filter_applied": {
            "circle": circle,
            "min_ccs_threshold": absolute_min,
            "effective_min_ccs": None if threshold is None else round(threshold, 2),
            "eligibility_mode": mode,
            "ccs_percentile": percentile if mode == "relative" else None,
            "eligibility_source_tag": source_tag,
            "planning_only": stamp is not None,
            "planning_stamp": stamp,
            "factory_target_mt": target_mt,
            "delta_only": delta_only
        },
        "queue_summary": {
            "total_queued_parcels": len(allocated),
            "total_queued_tonnage_mt": round(accumulated_mt, 1),
            "capacity_fulfillment_pct": round(min(accumulated_mt / max(target_mt, 1) * 100.0, 100.0), 1),
            "average_ccs_pct": avg_ccs,
            "average_brix_deg": avg_brix,
            "estimated_commercial_sugar_recovery_mt": est_sugar_mt,
            "transit_guarantee_hours": "< 18 Hours Cut-to-Crush",
            "eligibility_mode": mode,
            "effective_min_ccs": None if threshold is None else round(threshold, 2),
            "eligibility_source_tag": source_tag,
            "planning_stamp": stamp,
            "average_distance_km": avg_distance,
            "distance_method": "haversine" if "haversine" in methods else (next(iter(methods)) if len(methods) == 1 else None),
        },
        "parcels": parcels
    }

def get_plot_digital_health_slip(gat_no: str, eligibility_mode=None, min_ccs=None, ccs_percentile=None) -> dict:
    all_plots = get_calibrated_plots_list()
    clean_query = str(gat_no).strip().lower()
    
    match = None
    for p in all_plots:
        if str(p.get("gatNumber", "")).lower() == clean_query:
            match = p
            break
        if clean_query in str(p.get("gatNo", "")).lower():
            match = p
            break
        if clean_query in str(p.get("id", "")).lower():
            match = p
            break

    if not match:
        return None

    trajectory = build_plot_trajectory(match)
    farmer_mr = match.get("farmerMr", match.get("farmerEn", ""))
    village = match.get("village", "")
    variety = match.get("variety", "")
    cane_type = match.get("caneType", "")
    ccs = match.get("ccs", 11.2)
    brix = match.get("brix", 20.0)
    pol = match.get("pol", 15.0)
    tons = match.get("estTons", 35)
    acres = match.get("repAcres", 1.0)
    docket = match.get("docketId", f"DOK-{match.get('gatNumber', '000')}")

    settings = resolve_queue_settings(eligibility_mode, min_ccs, ccs_percentile)
    mode = settings["mode"]
    season_plots = [p for p in all_plots if not p.get("isGhost", False)]
    season_ccs = [_ccs_or_zero(p) for p in season_plots]
    if mode == "absolute":
        threshold = float(settings["min_ccs"])
    else:
        threshold = percentile_linear(season_ccs, settings["ccs_percentile"])
    plot_ccs = _ccs_or_zero(match)
    eligible = threshold is not None and plot_ccs + 1e-9 >= threshold
    kilometres, distance_meta = resolve_plot_distance(match, settings["mill"])
    travel = _travel_from_distance(match, kilometres)
    stamp = _planning_stamp(mode, settings["mill"])
    source_tag = "X" if mode == "relative" else "D"
    if mode == "absolute" and eligible:
        status_mr = "तोडणी योग्य (PEAK SUCROSE)"
        verdict = "READY_TO_CUT_PEAK_SUCROSE"
    elif eligible:
        status_mr = "या हंगामातील तुलनेने पिकलेला ऊस (RELATIVE RANK)"
        verdict = "READY_TO_CUT_SEASON_RELATIVE"
    else:
        status_mr = "१५ दिवसांत तोडणी"
        verdict = "MONITOR_15_DAYS"
    threshold_text = "n/a" if threshold is None else f"{threshold:.2f}"
    if kilometres is None:
        distance_text = "उपलब्ध नाही"
    else:
        distance_text = f"{kilometres} किमी ({distance_meta.get('method')}, tag {distance_meta.get('source_tag')})"
    percentile_rank = season_ccs_percentile(plot_ccs, season_ccs)

    whatsapp_text = (
        "🌾 *गंगामई सहकारी साखर कारखाना लि., शेवगाव*\n"
        "📋 *अधिकृत ऊस तोडणी आदेश (Cutting Slip)*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *शेतकरी:* {farmer_mr}\n"
        f"📍 *गट क्र.:* {match.get('gatNo')} (गाव: {village})\n"
        f"🌱 *वाण:* {variety} ({cane_type})\n"
        f"📐 *क्षेत्र:* {acres} एकर | *अंदाजे वजन:* {tons} मे. टन\n\n"
        "🛰️ *५-दिवसीय उपग्रह गुणवत्ता अहवाल (Sentinel-2)*:\n"
        f"• साखर उतारा (CCS): *{ccs}%*\n"
        f"• Brix: *{brix}°Bx* | Pol: *{pol}%*\n"
        f"• स्थिती: *{status_mr}*\n"
        f"• पात्रता: *{mode}* | CCS कट-ऑफ *{threshold_text}%* | season percentile *{percentile_rank}* | tag *{source_tag}*\n"
        f"• कारखान्यापासून अंतर: *{distance_text}* | mill point tag *{distance_meta.get('mill_point_source_tag')}*\n\n"
        "🚜 *तोडणी टोळी:* संतोष काळे मुकादम (ट्रॅक्टर ट्रॉली)\n"
        "⏱️ *वाहतूक मर्यादा:* १८ तास (तोडणी ते गाळप)\n"
        f"🎫 *डॉक्युमेंट क्र.:* {docket}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *सूचना:* कृपया तोडणीनंतर ऊस वाळू न देता तात्काळ कारखान्यात आणावा.\n"
        + (f"{stamp}\n" if stamp else "")
    )

    return {
        "status": "SUCCESS",
        "plot": match,
        "five_day_trajectory": trajectory,
        "harvest_recommendation": {
            "verdict": verdict,
            "recommended_window": "12-Oct-2026 to 18-Oct-2026" if eligible else "25-Oct-2026 to 05-Nov-2026",
            "assigned_gang": "Santosh Kale Mukadam (Tractor Fleet)",
            "max_transit_hours": 18,
            "eligibility_mode": mode,
            "effective_min_ccs": None if threshold is None else round(threshold, 2),
            "ccs_percentile": settings["ccs_percentile"] if mode == "relative" else None,
            "season_ccs_percentile": percentile_rank,
            "eligibility_source_tag": source_tag,
            "planning_only": stamp is not None,
            "planning_stamp": stamp,
            "distance_km": kilometres,
            "distance_method": distance_meta.get("method"),
            "distance_source_tag": distance_meta.get("source_tag"),
            "mill_point_source_tag": distance_meta.get("mill_point_source_tag"),
            "travel": travel,
        },
        "whatsapp_slip_text": whatsapp_text
    }
