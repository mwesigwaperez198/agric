from pydantic import BaseModel, Field


class ForecastPoint(BaseModel):
    date: str
    price: float
    lower_bound: float
    upper_bound: float


class PriceForecastOut(BaseModel):
    crop_name: str
    region: str
    currency: str
    current_price: float
    trend: str
    forecast: list[ForecastPoint]


class CropRecommendationOut(BaseModel):
    crop_name: str
    score: float
    confidence: str
    priority: str = "low"
    reasons: list[str]
    recommended: bool
    type: str = "annual"
    season: str = "all-year"
    ideal_temp: int = 25
    ideal_rain: int = 1000
    current_price: float | None = None


class MarketInsightOut(BaseModel):
    top_trends: list[dict]
    recommendations: list[CropRecommendationOut]


class CropInfoOut(BaseModel):
    name: str
    type: str
    ideal_temp: int
    ideal_rain: int
    season: str


class TranslationOut(BaseModel):
    dialect: str
    source: str
    translated: str
