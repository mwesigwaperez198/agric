from fastapi import APIRouter, HTTPException, Query

from api.app.deps import AnyRole, CurrentUser, DbSession
from api.app.models import PricePoint
from api.app.schemas.market import (
    CropInfoOut,
    CropRecommendationOut,
    ForecastPoint,
    MarketInsightOut,
    PriceForecastOut,
)
from api.app.services.market import forecast_prices, list_all_crops, recommend_crops, top_trends

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/crops", response_model=list[CropInfoOut])
def get_all_crops(user: AnyRole):
    """List all supported crops with agronomic metadata."""
    return [CropInfoOut(**c) for c in list_all_crops()]


@router.get("/forecast/{crop}", response_model=PriceForecastOut)
def price_forecast(crop: str, user: AnyRole, db: DbSession, region: str | None = None):
    data = forecast_prices(db, crop, region)
    if not data["forecast"]:
        raise HTTPException(status_code=404, detail="No price history for this crop")
    data["forecast"] = [ForecastPoint(**p) for p in data["forecast"]]
    return PriceForecastOut(**data)


@router.get("/insights", response_model=MarketInsightOut)
def market_insights(user: AnyRole, db: DbSession, region: str | None = None):
    return MarketInsightOut(
        top_trends=top_trends(db),
        recommendations=[CropRecommendationOut(**r) for r in recommend_crops(db, region)],
    )


@router.post("/price/seed")
def seed_price(db: DbSession, crop: str, region: str, price: float):
    db.add(PricePoint(crop_name=crop, region=region, price=price))
    db.commit()
    return {"ok": True, "crop": crop, "region": region, "price": price}
