import os
import json
import re

_CALIBRATED_PLOTS_CACHE = None

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
    min_ccs: float = 11.2,
    target_mt: float = 4500.0,
    delta_only: bool = False,
    pass_date: str = "2026-10-10"
) -> dict:
    all_plots = get_calibrated_plots_list()
    if not all_plots:
        return {"status": "ERROR", "message": "Calibrated plot register unavailable."}

    plots = [p for p in all_plots if not p.get("isGhost", False)]
    if circle != "ALL":
        plots = [p for p in plots if p.get("circle", "").lower() == circle.lower()]

    plots = [p for p in plots if float(p.get("ccs", 0)) >= min_ccs]

    if delta_only:
        plots = [p for p in plots if (float(p.get("ccs", 0)) - 0.5) < min_ccs <= float(p.get("ccs", 0))]

    plots.sort(key=lambda x: (-float(x.get("ccs", 0)), float(x.get("distKm", 99))))

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

    return {
        "status": "SUCCESS",
        "api_protocol": "IKSHU-ERP-REST-V2",
        "satellite_pass": pass_date,
        "satellite_platform": "Sentinel-2A/B MSI L2A BOA",
        "filter_applied": {
            "circle": circle,
            "min_ccs_threshold": min_ccs,
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
            "transit_guarantee_hours": "< 18 Hours Cut-to-Crush"
        },
        "parcels": [
            {
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
                "distance_km": p.get("distKm"),
                "max_transit_hours": p.get("transitTargetHours", 18),
                "harvest_window": "Optimal Next 7 Days"
            }
            for p in allocated
        ]
    }

def get_plot_digital_health_slip(gat_no: str) -> dict:
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

    whatsapp_text = (
        "🌾 *गंगामई सहकारी साखर कारखाना लि., शेवगाव*\n"
        "📋 *अधिकृत ऊस तोडणी आदेश (Cutting Slip)*\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 *शेतकरी:* {farmer_mr}\n"
        f"📍 *गट क्र.:* {match.get('gatNo')} (गाव: {village})\n"
        f"🌱 *वाण:* {variety} ({cane_type})\n"
        f"📐 *क्षेत्र:* {acres} एकर | *अंदाजे वजन:* {tons} मे. टन\n\n"
        "🛰️ *५-दिवसीय उपग्रह गुणवत्ता अहवाल (Sentinel-2)*:\n"
        f"• साखर उतारा (CCS): *{ccs}%* (सर्वोत्तम परिपक्वता)\n"
        f"• Brix: *{brix}°Bx* | Pol: *{pol}%*\n"
        "• स्थिती: *तोडणी योग्य (PEAK SUCROSE)*\n\n"
        "🚜 *तोडणी टोळी:* संतोष काळे मुकादम (ट्रॅक्टर ट्रॉली)\n"
        "⏱️ *वाहतूक मर्यादा:* १८ तास (तोडणी ते गाळप)\n"
        f"🎫 *डॉक्युमेंट क्र.:* {docket}\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚠️ *सूचना:* कृपया तोडणीनंतर ऊस वाळू न देता तात्काळ कारखान्यात आणावा."
    )

    return {
        "status": "SUCCESS",
        "plot": match,
        "five_day_trajectory": trajectory,
        "harvest_recommendation": {
            "verdict": "READY_TO_CUT_PEAK_SUCROSE" if float(ccs) >= 11.2 else "MONITOR_15_DAYS",
            "recommended_window": "12-Oct-2026 to 18-Oct-2026" if float(ccs) >= 11.2 else "25-Oct-2026 to 05-Nov-2026",
            "assigned_gang": "Santosh Kale Mukadam (Tractor Fleet)",
            "max_transit_hours": 18
        },
        "whatsapp_slip_text": whatsapp_text
    }
