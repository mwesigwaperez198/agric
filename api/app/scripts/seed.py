"""Database seed: demo farmer, consumer, farm, listings, price history, knowledge."""

import random
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from api.app.database import SessionLocal, init_db
from api.app.models import Farm, KnowledgeEntry, Listing, PricePoint, User
from api.app.security import hash_password

REGIONS = [("Kampala", 0.3476, 32.5825), ("Mbarara", -0.6072, 30.6545), ("Jinja", 0.4478, 33.2036)]

LISTING_SAMPLES = [
    ("Arabica Coffee (AA)", "coffee", "Arabica", 420, 12500, "AA"),
    ("Robusta Coffee", "coffee", "Robusta", 800, 6500, "B"),
    ("Maize", "grains", "Longe 5", 1500, 1850, "Grade 1"),
    ("Vanilla Beans", "other", "Planifolia", 90, 38000, "Premium"),
    ("Matooke Bananas", "produce", "East African Highland", 600, 2200, "Grade A"),
    ("Groundnuts", "grains", "Red Valencia", 350, 5200, "Grade 1"),
    ("Poultry (Layers)", "livestock", "ISA Brown", 120, 35000, "Ready"),
    ("Cocoa", "other", "Forastero", 260, 9800, "Fermented"),
]


def seed(db: Session) -> None:
    if db.query(User).count() > 0:
        print("Database already seeded, skipping.")
        return

    farmer = User(
        email="grace@novara.ug",
        full_name="Grace Nakato",
        phone="+256700000001",
        password_hash=hash_password("Farmer!Pass1"),
        role="farmer",
        is_verified=True,
    )
    consumer = User(
        email="daniel@novara.ug",
        full_name="Daniel Okello",
        phone="+256700000002",
        password_hash=hash_password("Buyer!Pass1"),
        role="consumer",
        is_verified=True,
    )
    admin = User(
        email="admin@novara.ug",
        full_name="NOVARA Admin",
        phone="+256700000003",
        password_hash=hash_password("Admin!Pass1"),
        role="admin",
        is_verified=True,
    )
    db.add_all([farmer, consumer, admin])
    db.flush()

    farm = Farm(
        owner_id=farmer.id,
        name="Kisoro Highlands Estate",
        description="Shade-grown Arabica at 1,600m with organic certification.",
        region="Mbarara",
        country="UG",
        latitude=-0.6072,
        longitude=30.6545,
        certifications="Organic, Rainforest Alliance",
    )
    db.add(farm)
    db.flush()

    for name, category, variety, qty, price, grade in LISTING_SAMPLES:
        region, lat, lon = REGIONS[random.randrange(len(REGIONS))]
        db.add(
            Listing(
                farm_id=farm.id,
                seller_id=farmer.id,
                crop_name=name,
                category=category,
                variety=variety,
                description=f"Fresh {name} from {farm.name}.",
                quantity=qty,
                unit="kg",
                price_per_unit=price,
                currency="UGX",
                quality_grade=grade,
                region=region,
                latitude=lat,
                longitude=lon,
                images=[],
            )
        )

    # 60 days of price history for forecasting
    now = datetime.now(UTC)
    for crop in ("coffee", "maize", "vanilla"):
        base = {"coffee": 11800, "maize": 1750, "vanilla": 36500}[crop]
        for i in range(60):
            db.add(
                PricePoint(
                    crop_name=crop,
                    region="national",
                    price=round(base * (1 + i * 0.002) * random.uniform(0.94, 1.06), 2),
                    currency="UGX",
                    source="seed",
                    recorded_at=now - timedelta(days=59 - i),
                )
            )

    knowledge = [
        KnowledgeEntry(topic="coffee leaf rust", crop_name="coffee", content="Wet warm weather spreads rust."),
        KnowledgeEntry(topic="moisture", crop_name="coffee", content="Store coffee near 11% moisture."),
        KnowledgeEntry(topic="ochratoxin", crop_name="coffee", content="OTA above 2ppb fails export limits."),
    ]
    db.add_all(knowledge)

    db.commit()
    print("Seeded: 2 users, 1 farm, 8 listings, 3 crops x 60 price points.")


if __name__ == "__main__":
    init_db()
    with SessionLocal() as session:
        seed(session)
