"""Market intelligence: price trend analysis, forecasting and weather-driven crop recommendations.

Forecasting uses a lightweight linear regression over recorded PricePoint history;
a production build can swap in a richer model without changing the router.
"""

import math
from collections import defaultdict
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy.orm import Session

from api.app.models import BiosensorReading, PricePoint

FORECAST_HORIZON_DAYS = 7

# ---------------------------------------------------------------------------
# Comprehensive agronomic fit: all major crops in Uganda / tropical Africa
# (ideal_temp_c, ideal_rain_mm_per_year, season, plant_type)
# plant_type: annual, perennial, tree, root, vegetable, fruit, spice
# ---------------------------------------------------------------------------

CROP_FIT: dict[str, dict] = {
    # Grains / Cereals
    "coffee": {"temp": 21, "rain": 1700, "season": "apr-oct", "type": "perennial", "ph_min": 6.0, "ph_max": 6.5},
    "maize": {"temp": 24, "rain": 800, "season": "feb-jul", "type": "annual", "ph_min": 5.5, "ph_max": 7.0},
    "rice": {"temp": 26, "rain": 1200, "season": "mar-jul", "type": "annual", "ph_min": 5.5, "ph_max": 6.5},
    "millet": {"temp": 27, "rain": 500, "season": "may-aug", "type": "annual", "ph_min": 5.5, "ph_max": 7.5},
    "sorghum": {"temp": 27, "rain": 600, "season": "may-aug", "type": "annual", "ph_min": 5.5, "ph_max": 8.0},
    "wheat": {"temp": 20, "rain": 600, "season": "oct-feb", "type": "annual", "ph_min": 6.0, "ph_max": 7.5},
    "teff": {"temp": 18, "rain": 700, "season": "jun-sep", "type": "annual", "ph_min": 5.5, "ph_max": 7.0},

    # Legumes / Pulses
    "beans": {"temp": 20, "rain": 900, "season": "mar-jun", "type": "annual", "ph_min": 6.0, "ph_max": 7.0},
    "groundnuts": {"temp": 25, "rain": 1000, "season": "may-aug", "type": "annual", "ph_min": 6.0, "ph_max": 7.0},
    "soybean": {"temp": 25, "rain": 900, "season": "mar-jul", "type": "annual", "ph_min": 6.0, "ph_max": 7.0},
    "cowpea": {"temp": 28, "rain": 500, "season": "may-aug", "type": "annual", "ph_min": 5.5, "ph_max": 7.0},
    "pigeon_pea": {"temp": 26, "rain": 600, "season": "mar-jul", "type": "perennial", "ph_min": 5.0, "ph_max": 8.0},
    "chickpea": {"temp": 22, "rain": 500, "season": "oct-feb", "type": "annual", "ph_min": 6.0, "ph_max": 8.0},
    "lentil": {"temp": 20, "rain": 400, "season": "oct-feb", "type": "annual", "ph_min": 6.0, "ph_max": 8.0},
    "cassava": {"temp": 25, "rain": 1000, "season": "all-year", "type": "root", "ph_min": 5.0, "ph_max": 7.0},

    # Root / Tuber
    "sweet_potato": {"temp": 24, "rain": 750, "season": "mar-jul", "type": "root", "ph_min": 5.5, "ph_max": 6.5},
    "irish_potato": {"temp": 18, "rain": 800, "season": "sep-dec", "type": "root", "ph_min": 5.0, "ph_max": 6.0},

    # Vegetables
    "tomato": {"temp": 24, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "onion": {"temp": 22, "rain": 400, "season": "jun-sep", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "cabbage": {"temp": 18, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.5},
    "chilli": {"temp": 25, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "okra": {"temp": 28, "rain": 600, "season": "mar-sep", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "eggplant": {"temp": 25, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 5.5, "ph_max": 6.5},
    "cucumber": {"temp": 25, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "capsicum": {"temp": 24, "rain": 600, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "spinach": {"temp": 20, "rain": 500, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.5},
    "lettuce": {"temp": 18, "rain": 500, "season": "all-year", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "amaranth": {"temp": 25, "rain": 500, "season": "all-year", "type": "vegetable", "ph_min": 5.5, "ph_max": 7.5},
    "pumpkin": {"temp": 25, "rain": 700, "season": "mar-aug", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},
    "watermelon": {"temp": 28, "rain": 500, "season": "oct-feb", "type": "vegetable", "ph_min": 6.0, "ph_max": 7.0},

    # Fruits
    "banana": {"temp": 26, "rain": 1500, "season": "all-year", "type": "fruit", "ph_min": 5.5, "ph_max": 7.0},
    "mango": {"temp": 27, "rain": 1000, "season": "all-year", "type": "tree", "ph_min": 5.0, "ph_max": 7.5},
    "avocado": {"temp": 22, "rain": 1200, "season": "all-year", "type": "tree", "ph_min": 5.5, "ph_max": 7.0},
    "pineapple": {"temp": 27, "rain": 1000, "season": "all-year", "type": "fruit", "ph_min": 4.5, "ph_max": 5.5},
    "papaya": {"temp": 28, "rain": 1000, "season": "all-year", "type": "tree", "ph_min": 5.5, "ph_max": 7.0},
    "passion_fruit": {"temp": 22, "rain": 1200, "season": "all-year", "type": "fruit", "ph_min": 5.0, "ph_max": 6.5},
    "jackfruit": {"temp": 27, "rain": 1200, "season": "all-year", "type": "tree", "ph_min": 6.0, "ph_max": 7.5},

    # Cash / Industrial
    "vanilla": {"temp": 27, "rain": 2200, "season": "all-year", "type": "spice", "ph_min": 6.0, "ph_max": 7.0},
    "tea": {"temp": 22, "rain": 1500, "season": "all-year", "type": "perennial", "ph_min": 4.5, "ph_max": 5.5},
    "cocoa": {"temp": 27, "rain": 1800, "season": "all-year", "type": "tree", "ph_min": 5.0, "ph_max": 7.5},
    "sugarcane": {"temp": 27, "rain": 1500, "season": "all-year", "type": "perennial", "ph_min": 6.0, "ph_max": 6.5},
    "cotton": {"temp": 27, "rain": 800, "season": "mar-jul", "type": "annual", "ph_min": 6.0, "ph_max": 8.0},
    "sesame": {"temp": 28, "rain": 500, "season": "may-aug", "type": "annual", "ph_min": 5.5, "ph_max": 8.0},
    "sunflower": {"temp": 25, "rain": 600, "season": "mar-jul", "type": "annual", "ph_min": 6.0, "ph_max": 7.5},
    "tobacco": {"temp": 24, "rain": 900, "season": "oct-feb", "type": "annual", "ph_min": 5.5, "ph_max": 6.5},
    "rubber": {"temp": 27, "rain": 1800, "season": "all-year", "type": "tree", "ph_min": 4.5, "ph_max": 6.0},

    # Nuts
    "macadamia": {"temp": 20, "rain": 1200, "season": "all-year", "type": "tree", "ph_min": 5.0, "ph_max": 6.5},
    "cashew": {"temp": 28, "rain": 1000, "season": "all-year", "type": "tree", "ph_min": 5.0, "ph_max": 7.0},

    # Spices / Herbs
    "ginger": {"temp": 25, "rain": 1500, "season": "mar-jul", "type": "spice", "ph_min": 5.5, "ph_max": 6.5},
    "turmeric": {"temp": 25, "rain": 1200, "season": "mar-jul", "type": "spice", "ph_min": 5.0, "ph_max": 7.5},
    "black_pepper": {"temp": 27, "rain": 2000, "season": "all-year", "type": "spice", "ph_min": 5.5, "ph_max": 6.5},
    "cinnamon": {"temp": 26, "rain": 2000, "season": "all-year", "type": "spice", "ph_min": 5.0, "ph_max": 7.0},
    "clove": {"temp": 27, "rain": 1800, "season": "all-year", "type": "spice", "ph_min": 5.5, "ph_max": 7.0},

    # Misc
    "peanut": {"temp": 25, "rain": 1000, "season": "may-aug", "type": "annual", "ph_min": 6.0, "ph_max": 7.0},
}


def _current_price(db: Session, crop_name: str, region: str | None = None) -> float | None:
    query = db.query(PricePoint).filter(PricePoint.crop_name == crop_name)
    if region:
        query = query.filter(PricePoint.region == region)
    point = query.order_by(PricePoint.recorded_at.desc()).first()
    return point.price if point else None


def forecast_prices(db: Session, crop_name: str, region: str | None = None) -> dict:
    query = (
        db.query(PricePoint)
        .filter(PricePoint.crop_name == crop_name)
        .order_by(PricePoint.recorded_at.asc())
    )
    if region:
        query = query.filter(PricePoint.region == region)
    points = query.limit(180).all()

    if not points:
        return {
            "crop_name": crop_name,
            "region": region or "national",
            "currency": "UGX",
            "current_price": None,
            "trend": "no_data",
            "forecast": [],
        }

    base = datetime.now(UTC).date()
    ts = np.array([(p.recorded_at.date() - base).days for p in points], dtype=float)
    prices = np.array([p.price for p in points], dtype=float)

    if len(points) < 3:
        trend = "stable"
        slope = 0.0
        noise = prices.std() or prices.mean() * 0.05
    else:
        slope, _ = np.polyfit(ts, prices, 1)
        residuals = prices - (slope * ts + (prices - slope * ts).mean())
        noise = float(residuals.std()) or prices.mean() * 0.05

    drift_pct = (slope / prices.mean()) * 100 if prices.mean() else 0
    trend = "up" if drift_pct > 1.5 else ("down" if drift_pct < -1.5 else "stable")

    forecast = []
    for day in range(1, FORECAST_HORIZON_DAYS + 1):
        projected = float(prices.mean()) + slope * day
        band = noise * math.sqrt(day)
        forecast.append(
            {
                "date": (base + timedelta(days=day)).isoformat(),
                "price": round(projected, 2),
                "lower_bound": round(projected - band, 2),
                "upper_bound": round(projected + band, 2),
            }
        )

    return {
        "crop_name": crop_name,
        "region": region or "national",
        "currency": points[0].currency,
        "current_price": float(points[-1].price),
        "trend": trend,
        "forecast": forecast,
    }


def weather_snapshot(db: Session) -> dict:
    """Approximate local climate from recent biosensor telemetry."""
    readings = db.query(BiosensorReading).order_by(BiosensorReading.received_at.desc()).limit(20).all()
    if not readings:
        return {"temperature_c": 22.0, "humidity_pct": 60.0, "rain_estimate_mm": 1200.0}
    temps = [r.payload.get("temperature_c") for r in readings if r.payload.get("temperature_c")]
    humid = [r.payload.get("humidity_pct") for r in readings if r.payload.get("humidity_pct")]
    mean = lambda seq: sum(seq) / len(seq) if seq else 0.0
    return {
        "temperature_c": round(mean(temps), 1),
        "humidity_pct": round(mean(humid), 1),
        "rain_estimate_mm": 1200.0,
    }


def recommend_crops(db: Session, region: str | None = None) -> list[dict]:
    """Score crops against observed climate, biosensor data, and market prices.

    Returns recommendations categorized by priority:
    - high: score >= 8 (strongly recommended)
    - moderate: score >= 5 (viable with some risk)
    - low: score < 5 (not recommended currently)
    """
    weather = weather_snapshot(db)

    # Get latest biosensor readings for additional context
    latest_readings = db.query(BiosensorReading).order_by(BiosensorReading.received_at.desc()).limit(5).all()
    avg_risk = 0.0
    if latest_readings:
        avg_risk = sum(r.risk_score for r in latest_readings) / len(latest_readings)

    results = []
    for crop, info in CROP_FIT.items():
        ideal_temp = info["temp"]
        ideal_rain = info["rain"]

        temp_penalty = abs(weather["temperature_c"] - ideal_temp)
        rain_penalty = abs(weather["rain_estimate_mm"] - ideal_rain) / 1000.0

        price = _current_price(db, crop, region)
        price_bonus = 0.6 if price else 0.3

        # Biosensor risk penalty: high risk readings = less suitable conditions
        risk_penalty = avg_risk * 0.3

        score = round(max(0.0, 10.0 - temp_penalty * 0.35 - rain_penalty * 1.4 - risk_penalty + price_bonus), 2)

        # Determine priority category
        if score >= 8:
            priority = "high"
        elif score >= 5:
            priority = "moderate"
        else:
            priority = "low"

        # Build detailed reasons
        reasons = []
        if temp_penalty <= 3:
            reasons.append(f"Ideal temperature: within {temp_penalty:.0f}C of {ideal_temp}C target")
        elif temp_penalty <= 8:
            reasons.append(f"Temperature marginal: {temp_penalty:.0f}C away from ideal {ideal_temp}C")
        else:
            reasons.append(f"Temperature unsuitable: {temp_penalty:.0f}C away from ideal {ideal_temp}C")

        reasons.append(f"Season: {info['season']}")
        reasons.append(f"Type: {info['type']}")

        if price:
            reasons.append(f"Current market price: UGX {price:,.0f}")
        else:
            reasons.append("No current market price data")

        if avg_risk > 2.0:
            reasons.append(f"Warning: elevated biosensor risk ({avg_risk:.1f}/5) in area")
        elif avg_risk > 0:
            reasons.append(f"Area biosensor readings normal ({avg_risk:.1f}/5)")

        results.append(
            {
                "crop_name": crop,
                "score": score,
                "confidence": "high" if score >= 8 else ("medium" if score >= 5 else "low"),
                "priority": priority,
                "reasons": reasons,
                "recommended": score >= 8,
                "type": info["type"],
                "season": info["season"],
                "ideal_temp": ideal_temp,
                "ideal_rain": ideal_rain,
                "current_price": price,
            }
        )

    results.sort(key=lambda r: r["score"], reverse=True)
    return results


def top_trends(db: Session, limit: int = 5) -> list[dict]:
    rows = db.query(PricePoint.crop_name, PricePoint.region).distinct().all()
    crops = {(r[0], r[1]) for r in rows}
    trends = []
    for crop, region in crops:
        f = forecast_prices(db, crop, region)
        if f["trend"] == "no_data" or not f["forecast"]:
            continue
        first, last = f["forecast"][0], f["forecast"][-1]
        change = ((last["price"] - first["price"]) / first["price"] * 100) if first["price"] else 0.0
        trends.append(
            {
                "crop_name": crop,
                "region": region or "national",
                "trend": f["trend"],
                "current_price": f["current_price"],
                "expected_change_pct": round(change, 1),
            }
        )
    trends.sort(key=lambda t: t["expected_change_pct"], reverse=True)
    return trends[:limit]


def list_all_crops() -> list[dict]:
    """Return all supported crops with their metadata for the frontend."""
    return [
        {
            "name": name,
            "type": info["type"],
            "ideal_temp": info["temp"],
            "ideal_rain": info["rain"],
            "season": info["season"],
        }
        for name, info in sorted(CROP_FIT.items())
    ]
