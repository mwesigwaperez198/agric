import math

from fastapi import APIRouter, HTTPException, Query, status

from api.app.deps import CurrentUser, DbSession, FarmerOnly
from api.app.models import Farm, Listing, User
from api.app.schemas.listing import ListingCreate, ListingOut

router = APIRouter(prefix="/listings", tags=["marketplace"])

EARTH_RADIUS_KM = 6371.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _enrich(listing: Listing, db: DbSession, lat: float | None = None, lon: float | None = None) -> ListingOut:
    out = ListingOut.model_validate(listing)
    seller = db.get(User, listing.seller_id)
    farm = db.get(Farm, listing.farm_id) if listing.farm_id else None
    out.seller_name = seller.full_name if seller else None
    out.farm_name = farm.name if farm else None
    if lat is not None and lon is not None and listing.latitude is not None and listing.longitude is not None:
        out.distance_km = round(_haversine_km(lat, lon, listing.latitude, listing.longitude), 1)
    return out


@router.get("", response_model=list[ListingOut])
def search_listings(
    db: DbSession,
    q: str | None = Query(default=None, max_length=120),
    category: str | None = None,
    region: str | None = None,
    crop: str | None = None,
    status_filter: str = Query(default="active", alias="status"),
    seller_id: int | None = None,
    max_distance_km: float | None = None,
    lat: float | None = None,
    lon: float | None = None,
    sort: str = Query(default="recent", pattern="^(recent|price_asc|price_desc|nearest)$"),
):
    query = db.query(Listing)
    if status_filter:
        query = query.filter(Listing.status == status_filter)
    if category:
        query = query.filter(Listing.category == category)
    if region:
        query = query.filter(Listing.region == region)
    if crop:
        query = query.filter(Listing.crop_name.ilike(f"%{crop}%"))
    if q:
        like = f"%{q.lower()}%"
        query = query.filter(
            Listing.crop_name.ilike(like) | Listing.description.ilike(like) | Listing.variety.ilike(like)
        )
    if seller_id:
        query = query.filter(Listing.seller_id == seller_id)

    listings = query.order_by(Listing.created_at.desc()).limit(200).all()
    enriched = [_enrich(l, db, lat, lon) for l in listings]

    if max_distance_km is not None and lat is not None and lon is not None:
        enriched = [e for e in enriched if e.distance_km is not None and e.distance_km <= max_distance_km]

    if sort == "price_asc":
        enriched.sort(key=lambda e: e.price_per_unit)
    elif sort == "price_desc":
        enriched.sort(key=lambda e: e.price_per_unit, reverse=True)
    elif sort == "nearest":
        enriched.sort(key=lambda e: e.distance_km if e.distance_km is not None else float("inf"))
    return enriched


@router.post("", response_model=ListingOut, status_code=status.HTTP_201_CREATED)
def create_listing(body: ListingCreate, user: FarmerOnly, db: DbSession):
    farm_id = body.farm_id
    if body.latitude is None or body.longitude is None or farm_id is None:
        farm = db.query(Farm).filter(Farm.owner_id == user.id).first()
        if farm is None:
            raise HTTPException(status_code=400, detail="Create a farm or supply farm_id first")
        farm_id = farm.id
        if body.latitude is None or body.longitude is None:
            body.latitude = farm.latitude
            body.longitude = farm.longitude
            body.region = body.region or farm.region
    if body.region is None and body.latitude is None:
        raise HTTPException(status_code=400, detail="region or farm coordinates are required")

    data = body.model_dump(exclude={"images", "farm_id"})
    data["images"] = body.images or []
    listing = Listing(seller_id=user.id, farm_id=farm_id, **data)
    db.add(listing)
    db.commit()
    db.refresh(listing)
    return _enrich(listing, db)


@router.get("/categories")
def categories(db: DbSession):
    rows = db.query(Listing.category).distinct().all()
    return [r[0] for r in rows if r[0]]


@router.get("/{listing_id}", response_model=ListingOut)
def get_listing(listing_id: int, db: DbSession):
    listing = db.get(Listing, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _enrich(listing, db)


@router.patch("/{listing_id}", response_model=ListingOut)
def update_listing(listing_id: int, patch: dict, user: FarmerOnly, db: DbSession):
    listing = db.get(Listing, listing_id)
    if not listing or listing.seller_id != user.id:
        raise HTTPException(status_code=404, detail="Listing not found")
    editable = {
        "crop_name", "category", "variety", "description", "quantity", "unit",
        "price_per_unit", "quality_grade", "harvest_date", "status", "images",
    }
    for key, value in patch.items():
        if key in editable:
            setattr(listing, key, value)
    db.commit()
    db.refresh(listing)
    return _enrich(listing, db)
