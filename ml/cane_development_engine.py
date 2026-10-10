"""
Cane Development Program (CDP) & Agronomic Advisory Engine — SatCane AI
========================================================================
Transforms satellite telemetry & cadastral parcel data into high-ROI agronomic interventions:
  Pillar 1: Varietal Diversification Advisory (recommends switching from CO-265 monoculture)
  Pillar 2: Drip Irrigation Subsidy Targeting & Water Deficit Scoring (LSWI / NDWI)
  Pillar 3: Nitrogen / Red-Edge Chlorophyll Advisory (NDRE-based top-dressing)
  Pillar 4: Ratoon (Khodwa) Management & Stubble Shaving Operations
  Pillar 5: Seed Nursery Certification (Nucleus Seed Plot Health)
"""
from typing import Dict, Any, List, Optional


class CaneDevelopmentEngine:
    """
    Evaluates a parcel's crop cycle, variety, moisture, and vigor trajectory to generate
    targeted Cane Development Program (CDP) recommendations and an agronomic health score (1-100).
    """

    @classmethod
    def evaluate_cdp_profile(
        cls,
        variety: str,
        cane_type: str,
        mean_ndvi: float,
        mean_ndre: float,
        mean_ccs: float,
        occupancy_pct: float,
        claimed_acres: float,
        is_ghost: bool = False
    ) -> Dict[str, Any]:
        """
        Generates full Cane Development Program advisory dossier for a Gat or plot.
        """
        if is_ghost:
            return {
                "cdp_health_score": 0,
                "subsidy_clearance_status": "LOCKED_GHOST_FRAUD",
                "subsidy_clearance_status_mr": "सबसिडी रोखली: बोगस नोंदणी (Subsidy Blocked)",
                "recommended_interventions": [
                    {
                        "priority": "HIGH",
                        "code": "REVOKE_ALL_ADVANCES",
                        "title": "Revoke All Factory Advances",
                        "title_mr": "सर्व उचल आणि बिबट वाटप रद्द करा",
                        "action": "Plot confirmed uncultivated. Immediate cancellation of seed, fertilizer, and drip subsidy."
                    }
                ],
                "drip_subsidy_recommendation": {
                    "eligible": False,
                    "reason": "Unplanted / zero-canopy bare soil."
                },
                "varietal_diversification_advisory": {
                    "current_variety": variety,
                    "target_recommendation": "N/A"
                },
                "ratoon_care_advisory": {
                    "is_ratoon": False,
                    "action_required": "None"
                }
            }

        # 1. Compute CDP Health Score (1 - 100)
        # Factors: Canopy Occupancy (35%), NDVI Vigor (35%), Sugar Maturation (20%), Red-Edge Nitrogen (10%)
        score = 0.0
        score += min(35.0, (occupancy_pct / 100.0) * 35.0)
        score += min(35.0, (mean_ndvi / 0.75) * 35.0)
        score += min(20.0, (mean_ccs / 12.5) * 20.0)
        score += min(10.0, (mean_ndre / 0.50) * 10.0)
        cdp_score = round(max(5.0, min(100.0, score)), 1)

        interventions = []

        # 2. Pillar 1: Varietal Diversification
        clean_var = str(variety).upper().strip()
        if "265" in clean_var:
            var_adv = {
                "current_variety": "CO-265 (Phule 265)",
                "risk_profile": "MONOCULTURE_SUSCEPTIBILITY",
                "risk_profile_mr": "मोनोकल्चर धोका (Monoculture Fungal Risk)",
                "recommendation": "Switch 30-50% area to early-maturing VSI-08005 or drought-tolerant PDN-15006 for phased crushing.",
                "recommendation_mr": "पुढील हंगामात ३०-५०% क्षेत्रावर VSI-08005 किंवा PDN-15006 लावावे."
            }
            interventions.append({
                "priority": "MEDIUM",
                "code": "VARIETY_DIVERSIFICATION",
                "title": "Varietal Re-balancing Incentive",
                "title_mr": "जाती बदल अनुदान (Varietal Shift)",
                "action": "Offer factory subsidy of ₹1,500/Acre on tissue-culture VSI-08005 seed sets for next planting."
            })
        else:
            var_adv = {
                "current_variety": clean_var,
                "risk_profile": "BALANCED_DIVERSIFIED",
                "risk_profile_mr": "संतुलित वाण (Diversified Variety)",
                "recommendation": "Maintain certified seed lineage. Eligible for Breeder Nursery Incentive.",
                "recommendation_mr": "प्रमाणित बेणे राखले आहे. रोपवाटिका अनुदानास पात्र."
            }

        # 3. Pillar 2: Drip Irrigation Deficit & Subsidy Clearance
        # If NDVI is between 0.35 and 0.60, the crop is salvageable with drip irrigation
        if 0.30 <= mean_ndvi < 0.65:
            drip_eligible = True
            drip_priority = "TOP_PRIORITY_DROUGHT_RESCUE"
            drip_action = f"Clear 80% Drip Irrigation Subsidy immediately. Parcel is water-stressed ({round(claimed_acres, 2)} Ac) but salvageable."
            drip_action_mr = f"तात्काळ ठिबक सिंचन अनुदान मंजूर करा ({round(claimed_acres, 2)} एकर). पीक दुष्काळातून वाचवता येईल."
            interventions.append({
                "priority": "HIGH",
                "code": "DRIP_SUBSIDY_APPROVED",
                "title": "Fast-Track Drip Irrigation Clearance",
                "title_mr": "तातडीने ठिबक सिंचन मंजुरी",
                "action": drip_action
            })
        elif mean_ndvi >= 0.65:
            drip_eligible = True
            drip_priority = "MAINTENANCE_STAGE"
            drip_action = "Good canopy vigor. Regular fertigation schedule recommended."
            drip_action_mr = "कॅनोपी उत्तम आहे. नियमित विद्राव्य खत वेळापत्रक ठेवावे."
        else:
            drip_eligible = False
            drip_priority = "UNECONOMICAL_SEVERE_STUNT"
            drip_action = "Crop severely stunted. Physical field inspection by CDO required before capital investment."
            drip_action_mr = "पीक अत्यंत खुंटलेले. ठिबक मंजुरीपूर्वी शेत पाहणी आवश्यक."

        # 4. Pillar 3: Nitrogen / Red-Edge Chlorophyll Top-Dressing
        if mean_ndre < 0.38:
            interventions.append({
                "priority": "HIGH",
                "code": "NITROGEN_CHLOROPHYLL_DEFICIT",
                "title": "Urea / Potash Top-Dressing Advisory",
                "title_mr": "युरिया व पोटॅश खत डोस शिफारस",
                "action": "NDRE indicates low chlorophyll (<0.38). Apply 50 kg Urea + 25 kg MOP (Muriate of Potash) per Acre with immediate irrigation."
            })

        # 5. Pillar 4: Ratoon (Khodwa) Management
        clean_cane_type = str(cane_type).capitalize()
        is_ratoon = "Khodwa" in clean_cane_type or "Ratoon" in clean_cane_type
        if is_ratoon:
            ratoon_adv = {
                "is_ratoon": True,
                "current_stage": "Ratoon Crop Maintenance",
                "recommended_practice": "Mechanized Stubble Shaving (बूड छाटणी) + Trash Shredding (पाचट कुजविणे) + 5kg Trichoderma.",
                "recommended_practice_mr": "बूड छाटणी, पाचट कुट्टी आणि ट्रायकोडर्मा वापरून पाचट जागेवर कुजवावे."
            }
            interventions.append({
                "priority": "MEDIUM",
                "code": "RATOON_STUBBLE_SHAVING",
                "title": "Ratoon Stubble & Trash Care",
                "title_mr": "खोडवा बूड छाटणी व पाचट व्यवस्थापन",
                "action": "Dispatch mill-subsidized tractor stubble shaver within 72 hours of harvest to ensure high tillering."
            })
        else:
            ratoon_adv = {
                "is_ratoon": False,
                "current_stage": "Plant Crop (लागण)",
                "recommended_practice": "Earthing-up (मोठी बांधणी) complete. Prepare drainage channels for monsoon.",
                "recommended_practice_mr": "मोठी बांधणी पूर्ण करावी. पाण्याचा निचरा होण्यासाठी सऱ्या मोकळ्या कराव्यात."
            }

        # 6. Overall Subsidy Status
        if cdp_score >= 60.0:
            subsidy_status = "APPROVED_HIGH_ROI_CANDIDATE"
            subsidy_status_mr = "मंजूर: उच्च परतावा पात्र शेतकरी (Approved High ROI)"
        elif cdp_score >= 35.0:
            subsidy_status = "CONDITIONAL_APPROVAL_RESCUE_REQUIRED"
            subsidy_status_mr = "सशर्त मंजूर: पीक सुधारणा आवश्यक (Conditional Approval)"
        else:
            subsidy_status = "HELD_REQUIRES_FIELD_INSPECTION"
            subsidy_status_mr = "स्थगित: प्रत्यक्ष तपासणी आवश्यक (Hold: Inspect)"

        return {
            "cdp_health_score": cdp_score,
            "subsidy_clearance_status": subsidy_status,
            "subsidy_clearance_status_mr": subsidy_status_mr,
            "recommended_interventions": interventions,
            "drip_subsidy_recommendation": {
                "eligible": drip_eligible,
                "priority_tier": drip_priority,
                "action_guidance": drip_action,
                "action_guidance_mr": drip_action_mr
            },
            "varietal_diversification_advisory": var_adv,
            "ratoon_care_advisory": ratoon_adv
        }
