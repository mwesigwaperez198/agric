"""Biosensor threat evaluation: multi-threat risk scoring for all crops."""

from api.app.models.biosensor import THREAT_LEVELS

# ---------------------------------------------------------------------------
# Per-crop tolerance limits (ppb / % / pH / ppm)
# Covers every major crop grown in Uganda + tropical Africa
# ---------------------------------------------------------------------------

LIMITS = {
    "coffee": {"ochratoxin_A_ppb": 2.0, "moisture_pct": 12.5},
    "maize": {"aflatoxin_B1_ppb": 10.0, "moisture_pct": 13.5},
    "vanilla": {"moisture_pct": 25.0},
    "cocoa": {"ochratoxin_A_ppb": 2.0, "moisture_pct": 7.5},
    "banana": {"moisture_pct": 15.0, "soil_ph": 6.0},
    "beans": {"moisture_pct": 14.0, "aflatoxin_B1_ppb": 10.0},
    "groundnuts": {"aflatoxin_B1_ppb": 10.0, "moisture_pct": 10.0},
    "soybean": {"moisture_pct": 13.0, "aflatoxin_B1_ppb": 20.0},
    "cassava": {"moisture_pct": 14.0, "hydrogen_cyanide_ppm": 50.0},
    "tea": {"moisture_pct": 10.0, "pesticide_residues_ppb": 30.0},
    "rice": {"moisture_pct": 14.0, "arsenic_ppm": 0.3},
    "millet": {"moisture_pct": 12.0, "aflatoxin_B1_ppb": 10.0},
    "sorghum": {"moisture_pct": 13.0, "aflatoxin_B1_ppb": 10.0},
    "sesame": {"moisture_pct": 9.0, "aflatoxin_B1_ppb": 10.0},
    "sunflower": {"moisture_pct": 10.0, "aflatoxin_B1_ppb": 10.0},
    "wheat": {"moisture_pct": 13.0, "moisture_loss_pct": 0.5},
    "sweet_potato": {"moisture_pct": 60.0, "soil_ph": 5.5},
    "irish_potato": {"moisture_pct": 78.0, "soil_ph": 5.2},
    "tomato": {"moisture_pct": 90.0, "soil_ph": 6.2},
    "onion": {"moisture_pct": 6.0, "soil_ph": 6.5},
    "chilli": {"moisture_pct": 12.0, "pesticide_residues_ppb": 30.0},
    "cabbage": {"moisture_pct": 90.0, "soil_ph": 6.5},
    "avocado": {"moisture_pct": 65.0, "soil_ph": 6.0},
    "mango": {"moisture_pct": 80.0, "soil_ph": 5.5},
    "pineapple": {"moisture_pct": 85.0, "soil_ph": 5.0},
    "papaya": {"moisture_pct": 88.0, "soil_ph": 6.0},
    "passion_fruit": {"moisture_pct": 80.0, "soil_ph": 5.5},
    "jackfruit": {"moisture_pct": 75.0, "soil_ph": 6.0},
    "watermelon": {"moisture_pct": 92.0, "soil_ph": 6.5},
    "pumpkin": {"moisture_pct": 90.0, "soil_ph": 6.0},
    "okra": {"moisture_pct": 88.0, "soil_ph": 6.5},
    "eggplant": {"moisture_pct": 90.0, "soil_ph": 6.0},
    "amaranth": {"moisture_pct": 85.0, "soil_ph": 6.0},
    "cucumber": {"moisture_pct": 95.0, "soil_ph": 6.0},
    "capsicum": {"moisture_pct": 90.0, "soil_ph": 6.0},
    "spinach": {"moisture_pct": 90.0, "soil_ph": 6.5},
    "lettuce": {"moisture_pct": 95.0, "soil_ph": 6.0},
    "ginger": {"moisture_pct": 60.0, "soil_ph": 5.8},
    "turmeric": {"moisture_pct": 50.0, "soil_ph": 5.5},
    "black_pepper": {"moisture_pct": 12.0, "pesticide_residues_ppb": 30.0},
    "cinnamon": {"moisture_pct": 12.0, "moisture_loss_pct": 0.3},
    "clove": {"moisture_pct": 10.0, "moisture_loss_pct": 0.2},
    "rubber": {"moisture_pct": 0.5, "moisture_loss_pct": 0.1},
    "cotton": {"moisture_pct": 8.0, "moisture_loss_pct": 0.5},
    "sugarcane": {"moisture_pct": 70.0, "soil_ph": 6.0},
    "tobacco": {"moisture_pct": 12.0, "arsenic_ppm": 1.0},
    "macadamia": {"moisture_pct": 3.5, "moisture_loss_pct": 0.3},
    "cashew": {"moisture_pct": 10.0, "aflatoxin_B1_ppb": 10.0},
    "peanut": {"aflatoxin_B1_ppb": 10.0, "moisture_pct": 10.0},
    "pigeon_pea": {"moisture_pct": 12.0, "aflatoxin_B1_ppb": 10.0},
    "cowpea": {"moisture_pct": 12.0, "aflatoxin_B1_ppb": 10.0},
    "lentil": {"moisture_pct": 12.0, "aflatoxin_B1_ppb": 10.0},
    "chickpea": {"moisture_pct": 12.0, "aflatoxin_B1_ppb": 10.0},
}

# ---------------------------------------------------------------------------
# Human-readable messages for each sensor parameter
# ---------------------------------------------------------------------------

MESSAGES = {
    "ochratoxin_A_ppb": "Ochratoxin A above safe limit — may cause kidney damage and trade rejection",
    "aflatoxin_B1_ppb": "Aflatoxin B1 above safe limit — carcinogenic, will fail export inspection",
    "moisture_pct": "Moisture content above safe drying target — risk of mold and spoilage",
    "pesticide_residues_ppb": "Pesticide residue load elevated — may exceed MRL for domestic/export",
    "soil_ph": "Soil pH outside optimal range — nutrient uptake impaired",
    "arsenic_ppm": "Arsenic above safe limit — health risk, will fail food safety standards",
    "hydrogen_cyanide_ppm": "Hydrogen cyanide (HCN) above safe limit — cassava must be properly processed",
    "moisture_loss_pct": "Moisture loss rate too high — reduce drying speed or improve storage",
}

# ---------------------------------------------------------------------------
# Crop-specific guidance: what to do when threats are detected
# ---------------------------------------------------------------------------

CROP_GUIDANCE: dict[str, dict[str, str]] = {
    "coffee": {
        "drying": "Sun-dry on raised beds to 12% moisture. Avoid ground drying. Turn beans every 2 hours.",
        "storage": "Store in clean, dry jute or sisal bags. Keep off floors on pallets. Temperature below 25C.",
        "sorting": "Remove black, sour, and insect-damaged beans before delivery. Grade AA/AB separately.",
        "mycotoxin": "Ochratoxin A forms during improper fermentation and drying. Ferment 48-72hrs in well-drained boxes.",
        "general": "Use certified seedlings (Ruiru 11, NARO 1). Apply 200g NPK per tree twice yearly.",
    },
    "maize": {
        "drying": "Dry to 13% moisture within 24 hours of harvest. Use hermetic bags (PICS) for storage.",
        "storage": "Aflatoxin risk increases with poor storage. Keep grain dry and ventilated. Fumigate if needed.",
        "sorting": "Remove discolored, broken, and weevil-damaged kernels before storage.",
        "mycotoxin": "Aflatoxin B1 is produced by Aspergillus fungi. Prevent by drying fast and storing dry.",
        "general": "Plant hybrid varieties (KH 600-23A, Longe 5). Space 75cm x 25cm. Apply DAP at planting.",
    },
    "banana": {
        "drying": "Bananas are not dried. Ensure proper bunch handling to avoid bruising and fungal entry.",
        "storage": "Store at 13-14C for ripening control. Keep away from ethylene-producing fruits.",
        "sorting": "Grade by size and remove damaged hands. Reject diseased bunches (Xanthomonas wilt).",
        "mycotoxin": "Low mycotoxin risk. Main threats are bacterial wilt and Fusarium wilt.",
        "general": "Use tissue-culture plantlets. De-sucker to 1 strong follower. Mulch heavily. Stake trees.",
    },
    "beans": {
        "drying": "Sun-dry to 12-13% moisture. Spread thinly on tarpaulins. Turn regularly.",
        "storage": "Store in hermetic bags. Cool, dry location. Weevil prevention with neem leaf ash.",
        "sorting": "Remove broken, discolored, and insect-damaged seeds.",
        "mycotoxin": "Aflatoxin risk exists. Ensure proper drying before storage.",
        "general": "Inoculate seed with Rhizobium. Rotate with cereals. Plant early to avoid bean fly.",
    },
    "groundnuts": {
        "drying": "Dry in pods to 10% moisture. Shell only when fully dry. Avoid mechanical damage.",
        "storage": "Shell and store in hermetic containers. High aflatoxin risk if stored damp.",
        "sorting": "Remove shriveled, discolored, and moldy kernels. Aflatoxin is invisible — test regularly.",
        "mycotoxin": "Groundnuts are HIGH RISK for aflatoxin. Dry immediately after harvest. Never store wet.",
        "general": "Plant early (May-June). Inoculate with rhizobium. Uproot whole plant to avoid kernel loss.",
    },
    "cocoa": {
        "drying": "Ferment beans 5-7 days in boxes, turning daily. Sun-dry on mats to 7% moisture.",
        "storage": "Store in dry, clean rooms in jute bags. Temperature below 25C, humidity below 60%.",
        "sorting": "Remove flat, mouldy, and insect-damaged beans. Grade by color and size.",
        "mycotoxin": "Ochratoxin A risk during fermentation. Ensure proper heap/box fermentation.",
        "general": "Shade young trees. Prune to single trunk. Apply NPK 3:2:1 twice yearly.",
    },
    "tea": {
        "drying": "Wither leaves 12-14 hours. Roll, ferment 2-3 hours, then fire to stop oxidation.",
        "storage": "Store processed tea in foil-lined containers away from moisture and strong odors.",
        "sorting": "Grade leaves by size and quality. Remove stems and coarse leaves.",
        "mycotoxin": "Pesticide residue is the primary safety concern. Observe pre-harvest intervals.",
        "general": "Pluck 2 leaves + 1 bud. Maintain hedge at 1.2m. Apply NPK every 6 weeks during flush.",
    },
    "cassava": {
        "drying": "Peel and chip/slice within 24 hours of harvest. Dry chips to 13% moisture.",
        "storage": "Fresh roots deteriorate in 48-72 hours. Process immediately into chips, flour, or gari.",
        "sorting": "Remove rotten, discolored, and worm-damaged roots before processing.",
        "mycotoxin": "HCN (cyanide) is the primary concern. Use low-cyanide varieties. Process properly.",
        "general": "Plant certified cuttings. Harvest 8-12 months after planting. Do not intercrop with beans.",
    },
    "soybean": {
        "drying": "Dry to 13% moisture. Sun-dry on tarpaulins. Combine when moisture is 13-15%.",
        "storage": "Store in clean, dry bags. Cool conditions. Weevil monitoring with neem.",
        "sorting": "Remove damaged, discolored, and shrunken seeds.",
        "mycotoxin": "Aflatoxin risk exists. Ensure proper drying. Test before sale.",
        "general": "Inoculate with Bradyrhizobium. Apply P and K. Do not apply N fertilizer.",
    },
    "rice": {
        "drying": "Dry paddy to 13% moisture within 24 hours. Use mechanical dryer if available.",
        "storage": "Store milled rice in jute or polypropylene bags. Cool, dry warehouse.",
        "sorting": "Remove paddy, chalky grains, and red streaked grains after milling.",
        "mycotoxin": "Arsenic contamination possible in irrigated rice. Test water source.",
        "general": "Level field for uniform water. Transplant 20-day seedlings. Maintain 5cm water depth.",
    },
    "tomato": {
        "drying": "Not dried. Harvest at breaker to mature stage for transport.",
        "storage": "Cool chain critical. Store at 10-13C. Avoid refrigeration below 7C (chilling injury).",
        "sorting": "Grade by size, color, and firmness. Reject cracked and diseased fruit.",
        "mycotoxin": "Low mycotoxin risk. Main concern is pesticide residue — observe PHI.",
        "general": "Stake or cage plants. Prune suckers. Irrigate consistently. Rotate with legumes.",
    },
    "avocado": {
        "drying": "Not dried. Harvest when mature. Ripen at 15-20C for 4-7 days.",
        "storage": "Cold storage at 5-7C extends shelf life to 3-4 weeks. Handle gently.",
        "sorting": "Grade by size (count) and external quality. Reject sunburned and damaged fruit.",
        "mycotoxin": "Minimal mycotoxin risk. Main concern is bruising and proper ripening.",
        "general": "Plant Hass or Fuerte varieties. Mulch around base. Prune for light penetration.",
    },
    "mango": {
        "drying": "Not dried. Harvest at physiological maturity. Ripen at 20-25C.",
        "storage": "Cold storage at 10-13C for 2-3 weeks. Ethylene treatment for uniform ripening.",
        "sorting": "Grade by size, color, and sap burn. Remove fruit with stone weevil damage.",
        "mycotoxin": "Minimal risk. Anthracnose and stem-end rot are primary post-harvest diseases.",
        "general": "Prune annually after fruiting. Apply copper spray for anthracnose. Thin fruit clusters.",
    },
    "sugarcane": {
        "drying": "Not dried. Cut and crush within 24 hours for best sugar content (Brix).",
        "storage": "Cut cane loses 1-2% sugar per day. Process immediately or cover to prevent sun drying.",
        "sorting": "Remove burnt, diseased, and top portions. Use mid-section for crushing.",
        "mycotoxin": "Low mycotoxin risk. Main concern is fermentation and sugar loss.",
        "general": "Plant setts in furrows. Apply heavy N doses. Ratoon crop for 2-3 seasons.",
    },
}

# Default guidance for crops not in CROP_GUIDANCE
_DEFAULT_GUIDANCE = {
    "drying": "Dry harvested produce to safe moisture levels for your crop type. Use sun drying or mechanical dryers.",
    "storage": "Store in clean, dry, well-ventilated area. Use hermetic storage for grains and legumes.",
    "sorting": "Remove damaged, discolored, and diseased produce before storage or sale.",
    "mycotoxin": "Ensure proper drying and storage to minimize mycotoxin contamination.",
    "general": "Follow recommended agronomic practices for your region. Consult your local extension officer.",
}


def get_guidance(crop_name: str) -> dict[str, str]:
    """Return crop-specific handling guidance, falling back to defaults."""
    return CROP_GUIDANCE.get(crop_name.lower(), _DEFAULT_GUIDANCE)


# ---------------------------------------------------------------------------
# Threat evaluation engine
# ---------------------------------------------------------------------------


def evaluate(payload: dict, crop_name: str = "coffee") -> tuple[str, list[dict], float]:
    """Returns (threat_level, threats, risk_score)."""
    crop = crop_name.lower().strip()
    limits = LIMITS.get(crop, LIMITS.get("coffee", {}))
    threats: list[dict] = []
    score = 0.0

    for key, limit in limits.items():
        raw = payload.get(key)
        if raw is None:
            continue
        try:
            value = float(raw)
        except (TypeError, ValueError):
            continue
        if value > limit:
            ratio = value / limit
            level = "critical" if ratio > 2.0 else ("warning" if ratio > 1.4 else "watch")
            threats.append(
                {
                    "code": key,
                    "label": key,
                    "level": level,
                    "value": value,
                    "limit": limit,
                    "message": MESSAGES.get(key, "Reading outside safe range"),
                }
            )
            score += min(ratio, 3.0)

    residue = payload.get("pesticide_residues_ok")
    if residue is False:
        threats.append(
            {
                "code": "pesticide_residues_ppb",
                "label": "pesticide_residues_ppb",
                "level": "watch",
                "value": payload.get("pesticide_residues_ppb"),
                "limit": 30,
                "message": MESSAGES["pesticide_residues_ppb"],
            }
        )
        score += 0.8

    if not threats:
        level = "safe"
    elif score >= 3.0:
        level = "critical"
    elif score >= 1.6:
        level = "warning"
    else:
        level = "watch"

    level = level if level in THREAT_LEVELS else "watch"
    return level, threats, round(min(score, 5.0), 2)
