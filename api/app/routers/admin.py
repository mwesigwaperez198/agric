from collections import Counter

from fastapi import APIRouter, HTTPException

from api.app.deps import AdminOnly, DbSession
from api.app.models import BiosensorReading, Listing, Order, User
from api.app.models.trade import EscrowLedger

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats")
def platform_stats(admin: AdminOnly, db: DbSession):
    return {
        "users": db.query(User).count(),
        "listings": db.query(Listing).count(),
        "orders": db.query(Order).count(),
        "escrow_entries": db.query(EscrowLedger).count(),
        "biosensor_readings": db.query(BiosensorReading).count(),
        "commission_total": round(
            sum(o.commission_amount for o in db.query(Order).filter(Order.status == "settled").all()), 2
        ),
    }


@router.get("/ledger/verify/{order_id}")
def verify_ledger(order_id: int, admin: AdminOnly, db: DbSession):
    """Recomputes the SHA-256 chain for an order's escrow ledger."""
    from api.app.security import ledger_hash

    rows = (
        db.query(EscrowLedger)
        .filter(EscrowLedger.order_id == order_id)
        .order_by(EscrowLedger.id.asc())
        .all()
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No ledger for order")
    prev = "GENESIS"
    for row in rows:
        import json

        from datetime import UTC, datetime

        payload = json.dumps(
            {
                "order_id": row.order_id,
                "type": row.entry_type,
                "amount": row.amount,
                "balance_after": row.balance_after,
                "reference": row.reference,
                "ts": row.created_at.isoformat() if row.created_at.tzinfo else row.created_at.replace(tzinfo=UTC).isoformat(),
            },
            sort_keys=True,
        )
        expected = ledger_hash(prev, payload)
        if expected != row.sha256_hash:
            return {"verified": False, "broken_at": row.id, "expected": expected, "stored": row.sha256_hash}
        prev = expected
    return {"verified": True, "order_id": order_id, "tail_hash": prev}


@router.get("/threats/summary")
def threat_summary(admin: AdminOnly, db: DbSession):
    levels = [r.threat_level for r in db.query(BiosensorReading).all()]
    return {"threat_levels": dict(Counter(levels)), "total": len(levels)}
