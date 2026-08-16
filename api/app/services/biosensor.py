"""Biosensor threat evaluation: multi-threat risk scoring."""

from api.app.models.biosensor import THREAT_LEVELS

# Per-crop tolerance limits in parts-per-billion / percent.
LIMITS = {
    "coffee": {"ochratoxin_A_ppb": 2.0, "moisture_pct": 12.5},
    "maize": {"aflatoxin_B1_ppb": 10.0, "moisture_pct": 13.5},
    "vanilla": {"moisture_pct": 25.0},
    "cocoa": {"ochratoxin_A_ppb": 2.0, "moisture_pct": 7.5},
}

MESSAGES = {
    "ochratoxin_A_ppb": "Ochratoxin A above safe limit for this crop",
    "aflatoxin_B1_ppb": "Aflatoxin B1 above safe limit for this crop",
    "moisture_pct": "Moisture content above drying target",
    "pesticide_residues_ppb": "Pesticide residue load elevated",
}


def evaluate(payload: dict, crop_name: str = "coffee") -> tuple[str, list[dict], float]:
    """Returns (threat_level, threats, risk_score)."""
    limits = LIMITS.get(crop_name.lower(), LIMITS["coffee"])
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

    # Clamp to known levels
    level = level if level in THREAT_LEVELS else "watch"
    return level, threats, round(min(score, 5.0), 2)
