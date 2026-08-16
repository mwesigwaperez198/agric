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
    reasons: list[str]
    recommended: bool


class MarketInsightOut(BaseModel):
    top_trends: list[dict]
    recommendations: list[CropRecommendationOut]


class TranslationOut(BaseModel):
    dialect: str
    source: str
    translated: str
