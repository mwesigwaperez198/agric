from fastapi import APIRouter, HTTPException, status

from api.app.deps import AnyRole, CurrentUser, DbSession
from api.app.models import Listing
from api.app.models.trade import Order
from api.app.schemas.trade import ConfirmDeliveryRequest, OrderCreate, OrderOut
from api.app.services.commission import split_transaction
from api.app.services.escrow import (
    charge_commission,
    deposit_funds,
    refund_buyer,
    release_to_farmer,
)

router = APIRouter(prefix="/orders", tags=["orders"])


def _out(order: Order) -> OrderOut:
    return OrderOut.model_validate(order)


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(body: OrderCreate, user: AnyRole, db: DbSession):
    listing = db.get(Listing, body.listing_id)
    if not listing or listing.status != "active":
        raise HTTPException(status_code=404, detail="Listing unavailable")
    if listing.seller_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")
    if body.quantity > listing.quantity:
        raise HTTPException(status_code=400, detail=f"Only {listing.quantity} {listing.unit} available")

    total = round(body.quantity * listing.price_per_unit, 2)
    commission, farmer_net = split_transaction(total)
    order = Order(
        buyer_id=user.id,
        listing_id=listing.id,
        seller_id=listing.seller_id,
        quantity=body.quantity,
        unit_price=listing.price_per_unit,
        total=total,
        currency=listing.currency,
        commission_rate=round(commission / total, 4) if total else 0.0,
        commission_amount=commission,
        farmer_net=farmer_net,
        status="in_escrow",
        delivery_notes=body.delivery_notes,
    )
    db.add(order)
    db.flush()

    deposit_funds(db, order, total)  # mock mobile-money deposit
    listing.quantity = round(listing.quantity - body.quantity, 3)
    if listing.quantity <= 0:
        listing.status = "sold_out"

    db.commit()
    db.refresh(order)
    return _out(order)


@router.get("", response_model=list[OrderOut])
def list_orders(user: CurrentUser, db: DbSession, status_filter: str | None = None):
    query = db.query(Order).filter((Order.buyer_id == user.id) | (Order.seller_id == user.id))
    if status_filter:
        query = query.filter(Order.status == status_filter)
    return [_out(o) for o in query.order_by(Order.created_at.desc()).limit(100).all()]


@router.get("/{order_id}", response_model=OrderOut)
def get_order(order_id: int, user: CurrentUser, db: DbSession):
    order = db.get(Order, order_id)
    if not order or (order.buyer_id != user.id and order.seller_id != user.id):
        raise HTTPException(status_code=404, detail="Order not found")
    return _out(order)


@router.post("/{order_id}/confirm", response_model=OrderOut)
def confirm_delivery(order_id: int, body: ConfirmDeliveryRequest, user: CurrentUser, db: DbSession):
    order = db.get(Order, order_id)
    if not order or order.buyer_id != user.id:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("in_escrow", "shipped"):
        raise HTTPException(status_code=400, detail="Order is not awaiting confirmation")

    order.delivery_proof_url = body.proof_url
    order.delivery_notes = body.note or order.delivery_notes
    charge_commission(db, order)          # deduct platform % from escrow
    release_to_farmer(db, order)          # push farmer net to wallet
    order.status = "settled"
    db.commit()
    db.refresh(order)
    return _out(order)


@router.post("/{order_id}/cancel", response_model=OrderOut)
def cancel_order(order_id: int, user: CurrentUser, db: DbSession):
    order = db.get(Order, order_id)
    if not order or (order.buyer_id != user.id and order.seller_id != user.id):
        raise HTTPException(status_code=404, detail="Order not found")
    if order.status not in ("in_escrow", "pending"):
        raise HTTPException(status_code=400, detail="Order cannot be cancelled")

    refund_buyer(db, order)
    order.status = "cancelled"
    listing = db.get(Listing, order.listing_id)
    if listing:
        listing.quantity = round(listing.quantity + order.quantity, 3)
        if listing.status == "sold_out":
            listing.status = "active"
    db.commit()
    db.refresh(order)
    return _out(order)
