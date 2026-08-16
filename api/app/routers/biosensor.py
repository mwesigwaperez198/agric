from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from api.app.deps import AnyRole, CurrentUser, DbSession
from api.app.models import BiosensorReading
from api.app.schemas.biosensor import BiosensorOut, BiosensorPayload, BiosensorSeries, Threat
from api.app.services.biosensor import evaluate

router = APIRouter(prefix="/biosensor", tags=["biosensor"])


def _out(reading: BiosensorReading) -> BiosensorOut:
    return BiosensorOut.model_validate(reading)


@router.post("/readings", response_model=BiosensorOut, status_code=201)
def ingest_reading(body: BiosensorPayload, user: CurrentUser, db: DbSession):
    """Accepts raw multi-threat payloads and evaluates threat levels."""
    level, threats, score = evaluate(body.payload, body.crop_name)
    reading = BiosensorReading(
        device_id=body.device_id,
        farm_id=body.farm_id,
        crop_name=body.crop_name,
        batch_id=body.batch_id,
        payload=body.payload,
        threat_level=level,
        threats=[Threat(**t).model_dump() for t in threats],
        risk_score=score,
        read_at=body.read_at or datetime.now(UTC),
    )
    db.add(reading)
    db.commit()
    db.refresh(reading)
    return _out(reading)


@router.post("/readings/raw", response_model=BiosensorOut, status_code=201)
def ingest_raw(body: BiosensorPayload, user: AnyRole, db: DbSession):
    """Alias accepting the Phase-1 mock generator JSON directly."""
    return ingest_reading(body, user, db)


@router.get("/readings", response_model=list[BiosensorOut])
def list_readings(
    user: CurrentUser,
    db: DbSession,
    device_id: str | None = None,
    crop: str | None = None,
    limit: int = Query(default=50, le=500),
):
    query = db.query(BiosensorReading)
    if device_id:
        query = query.filter(BiosensorReading.device_id == device_id)
    if crop:
        query = query.filter(BiosensorReading.crop_name == crop)
    rows = query.order_by(BiosensorReading.received_at.desc()).limit(limit).all()
    return [_out(r) for r in rows]


@router.get("/series", response_model=BiosensorSeries)
def device_series(user: CurrentUser, db: DbSession, device_id: str, limit: int = Query(default=100, le=500)):
    rows = (
        db.query(BiosensorReading)
        .filter(BiosensorReading.device_id == device_id)
        .order_by(BiosensorReading.received_at.asc())
        .limit(limit)
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No readings for device")
    return BiosensorSeries(
        device_id=device_id, crop_name=rows[-1].crop_name, readings=[_out(r) for r in rows]
    )


@router.get("/latest", response_model=BiosensorOut)
def latest_reading(user: CurrentUser, db: DbSession, device_id: str | None = None):
    query = db.query(BiosensorReading)
    if device_id:
        query = query.filter(BiosensorReading.device_id == device_id)
    reading = query.order_by(BiosensorReading.received_at.desc()).first()
    if not reading:
        raise HTTPException(status_code=404, detail="No readings yet")
    return _out(reading)
