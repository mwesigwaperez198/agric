"""Market intelligence: price trend analysis, forecasting and crop recommendations.

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

# Simplified agronomic fit: crop_name -> (ideal_temp_c, ideal_rain_mm, season)
CROP_FIT = {
    "coffee": (21, 1700, "apr-oct"),
    "maize": (24, 800, "feb-jul"),
    "vanilla": (27, 2200, "all-year"),
    "banana": (26, 1500, "all-year"),
    "groundnuts": (25, 1000, "may-aug"),
    "beans": (20, 900, "mar-jun"),
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
    """Approximate local climate from recent biosensor telemetry (mock weather)."""
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
    """Score crops against observed climate and recent local prices."""
    weather = weather_snapshot(db)
    results = []
    for crop, (ideal_temp, ideal_rain, season) in CROP_FIT.items():
        temp_penalty = abs(weather["temperature_c"] - ideal_temp)
        rain_penalty = abs(weather["rain_estimate_mm"] - ideal_rain) / 1000.0
        price = _current_price(db, crop, region) or 0.0
        price_bonus = 0.6 if price else 0.3
        score = round(max(0.0, 10.0 - temp_penalty * 0.35 - rain_penalty * 1.4 + price_bonus), 2)
        results.append(
            {
                "crop_name": crop,
                "score": score,
                "confidence": "high" if score >= 8 else ("medium" if score >= 6.5 else "low"),
                "reasons": [
                    f"Within {temp_penalty:.0f}C of ideal temperature ({ideal_temp}C)",
                    f"Seasonality: {season}",
                    "Recent regional price supports demand" if price else "Limited local price history",
                ],
                "recommended": score >= 8,
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
