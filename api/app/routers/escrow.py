from fastapi import APIRouter, HTTPException

from api.app.deps import CurrentUser, DbSession
from api.app.models.trade import EscrowLedger, Order
from api.app.schemas.trade import LedgerEntryOut
from api.app.services.escrow import escrow_balance

router = APIRouter(prefix="/orders", tags=["escrow"])


@router.get("/{order_id}/ledger", response_model=list[LedgerEntryOut])
def order_ledger(order_id: int, user: CurrentUser, db: DbSession):
    order = db.get(Order, order_id)
    if not order or (order.buyer_id != user.id and order.seller_id != user.id):
        raise HTTPException(status_code=404, detail="Order not found")
    rows = (
        db.query(EscrowLedger)
        .filter(EscrowLedger.order_id == order_id)
        .order_by(EscrowLedger.id.asc())
        .all()
    )
    return [LedgerEntryOut.model_validate(r) for r in rows]


@router.get("/{order_id}/balance")
def order_balance(order_id: int, user: CurrentUser, db: DbSession):
    order = db.get(Order, order_id)
    if not order or (order.buyer_id != user.id and order.seller_id != user.id):
        raise HTTPException(status_code=404, detail="Order not found")
    return {"order_id": order_id, "escrow_balance": escrow_balance(db, order_id)}
