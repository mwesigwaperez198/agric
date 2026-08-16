from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from api.app.models.listing import CROP_CATEGORIES


class ListingCreate(BaseModel):
    farm_id: int | None = None
    crop_name: str = Field(min_length=2, max_length=120)
    category: str = Field(default="other", pattern="^(" + "|".join(CROP_CATEGORIES) + ")$")
    variety: str | None = Field(default=None, max_length=120)
    description: str | None = None
    quantity: float = Field(gt=0)
    unit: str = "kg"
    price_per_unit: float = Field(gt=0)
    currency: str = "UGX"
    quality_grade: str | None = None
    harvest_date: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    region: str | None = None
    images: list[str] = []


class ListingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    farm_id: int
    seller_id: int
    crop_name: str
    category: str
    variety: str | None
    description: str | None
    quantity: float
    unit: str
    price_per_unit: float
    currency: str
    quality_grade: str | None
    harvest_date: str | None
    latitude: float | None
    longitude: float | None
    region: str | None
    images: list[str]
    status: str
    created_at: datetime
    total_value: float

    seller_name: str | None = None
    farm_name: str | None = None
    distance_km: float | None = None
