"""Real-time weather data from OpenWeatherMap for Ugandan farmers."""

import logging
import time

import httpx

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[float, dict]] = {}
_CACHE_TTL = 900  # 15 minutes


def _cache_key(lat: float, lon: float) -> str:
    return f"{round(lat, 2)},{round(lon, 2)}"


def get_current_weather(lat: float, lon: float, api_key: str) -> dict | None:
    """Fetch current weather from OpenWeatherMap. Returns None on failure."""
    from api.app.config import settings

    key = api_key or settings.openweather_api_key
    if not key:
        return None

    ck = _cache_key(lat, lon)
    if ck in _cache:
        ts, data = _cache[ck]
        if time.time() - ts < _CACHE_TTL:
            return data

    try:
        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()
        result = {
            "temp": round(raw["main"]["temp"], 1),
            "feels_like": round(raw["main"]["feels_like"], 1),
            "humidity": raw["main"]["humidity"],
            "description": raw["weather"][0]["description"].title(),
            "wind_speed": round(raw.get("wind", {}).get("speed", 0) * 3.6, 1),
            "rain_1h": raw.get("rain", {}).get("1h", 0),
            "clouds": raw.get("clouds", {}).get("all", 0),
            "visibility": raw.get("visibility", 0) / 1000,
        }
        _cache[ck] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("OpenWeatherMap current weather failed: %s", e)
        return None


def get_forecast(lat: float, lon: float, api_key: str) -> list[dict] | None:
    """Fetch 5-day/3-hour forecast. Returns list of daily summaries or None."""
    from api.app.config import settings

    key = api_key or settings.openweather_api_key
    if not key:
        return None

    ck = f"fc:{_cache_key(lat, lon)}"
    if ck in _cache:
        ts, data = _cache[ck]
        if time.time() - ts < _CACHE_TTL:
            return data

    try:
        resp = httpx.get(
            "https://api.openweathermap.org/data/2.5/forecast",
            params={"lat": lat, "lon": lon, "appid": key, "units": "metric"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()

        daily: dict[str, dict] = {}
        for item in raw.get("list", []):
            date = item["dt_txt"][:10]
            if date not in daily:
                daily[date] = {
                    "date": date,
                    "temp_min": item["main"]["temp_min"],
                    "temp_max": item["main"]["temp_max"],
                    "descriptions": [],
                    "rain_chance": 0,
                    "rain_mm": 0,
                }
            d = daily[date]
            d["temp_min"] = min(d["temp_min"], item["main"]["temp_min"])
            d["temp_max"] = max(d["temp_max"], item["main"]["temp_max"])
            desc = item["weather"][0]["description"].title()
            if desc not in d["descriptions"]:
                d["descriptions"].append(desc)
            pop = item.get("pop", 0)
            if pop > d["rain_chance"]:
                d["rain_chance"] = pop
            d["rain_mm"] += item.get("rain", {}).get("3h", 0)

        result = list(daily.values())[:5]
        for d in result:
            d["temp_min"] = round(d["temp_min"], 1)
            d["temp_max"] = round(d["temp_max"], 1)
            d["rain_mm"] = round(d["rain_mm"], 1)
            d["rain_chance"] = round(d["rain_chance"] * 100)
            d["description"] = ", ".join(d["descriptions"][:2])
            del d["descriptions"]

        _cache[ck] = (time.time(), result)
        return result
    except Exception as e:
        logger.warning("OpenWeatherMap forecast failed: %s", e)
        return None


def format_weather_context(lat: float, lon: float, location_name: str = "") -> str:
    """Build a weather context block for the AI prompt."""
    from api.app.config import settings

    if not settings.openweather_api_key:
        return ""

    current = get_current_weather(lat, lon, settings.openweather_api_key)
    forecast = get_forecast(lat, lon, settings.openweather_api_key)
    if not current:
        return ""

    lines = ["[LIVE WEATHER DATA]"]
    if location_name:
        lines.append(f"Location: {location_name} ({lat}, {lon})")

    rain_status = ""
    if current["rain_1h"] > 0:
        rain_status = f", Raining now ({current['rain_1h']}mm/hr)"
    elif current["clouds"] > 70:
        rain_status = ", Overcast"
    elif current["clouds"] < 20:
        rain_status = ", Clear skies"

    lines.append(
        f"Current: {current['temp']}C (feels {current['feels_like']}C), "
        f"{current['description']}, Humidity {current['humidity']}%, "
        f"Wind {current['wind_speed']} km/h{rain_status}"
    )

    if forecast:
        lines.append("5-day forecast:")
        for d in forecast:
            rain_info = f", Rain {d['rain_chance']}%" if d["rain_chance"] > 10 else ""
            lines.append(
                f"  {d['date']}: {d['temp_min']}-{d['temp_max']}C, "
                f"{d['description']}{rain_info}"
            )

    lines.append("[/LIVE WEATHER DATA]")
    return "\n".join(lines) + "\n\n"
