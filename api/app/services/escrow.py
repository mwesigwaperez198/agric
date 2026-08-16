"""Escrow ledger with SHA-256 chained hashing for tamper-evident fund flow."""

import json
import secrets
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from api.app.config import settings
from api.app.models.trade import EscrowLedger, Order, Wallet
from api.app.security import ledger_hash


def _wallet(db: Session, user_id: int) -> Wallet:
    wallet = db.query(Wallet).filter(Wallet.user_id == user_id).one_or_none()
    if wallet is None:
        wallet = Wallet(user_id=user_id, balance=0.0, currency=settings.currency)
        db.add(wallet)
        db.flush()
    return wallet


def get_wallet(db: Session, user_id: int) -> Wallet:
    return _wallet(db, user_id)


def _ledger_head(db: Session, order_id: int) -> str:
    last = (
        db.query(EscrowLedger)
        .filter(EscrowLedger.order_id == order_id)
        .order_by(EscrowLedger.id.desc())
        .first()
    )
    return last.sha256_hash if last else "GENESIS"


def _append_entry(
    db: Session,
    order_id: int,
    entry_type: str,
    amount: float,
    balance_after: float,
    note: str | None,
) -> EscrowLedger:
    prev_hash = _ledger_head(db, order_id)
    reference = f"ord-{order_id}:{entry_type}:{secrets.token_hex(6)}"
    ts = datetime.now(UTC)
    payload = json.dumps(
        {
            "order_id": order_id,
            "type": entry_type,
            "amount": amount,
            "balance_after": balance_after,
            "reference": reference,
            "ts": ts.isoformat(),
        },
        sort_keys=True,
    )
    entry = EscrowLedger(
        order_id=order_id,
        entry_type=entry_type,
        amount=round(amount, 2),
        balance_after=round(balance_after, 2),
        reference=reference,
        prev_hash=prev_hash,
        sha256_hash=ledger_hash(prev_hash, payload),
        note=note,
        created_at=ts.replace(tzinfo=None),
    )
    db.add(entry)
    db.flush()
    return entry


def escrow_balance(db: Session, order_id: int) -> float:
    last = (
        db.query(EscrowLedger)
        .filter(EscrowLedger.order_id == order_id)
        .order_by(EscrowLedger.id.desc())
        .first()
    )
    return last.balance_after if last else 0.0


def deposit_funds(db: Session, order: Order, amount: float) -> EscrowLedger:
    """Buyer funds move into escrow at order placement."""
    balance = escrow_balance(db, order.id) + amount
    return _append_entry(db, order.id, "deposit", amount, balance, "Buyer deposit into escrow")


def charge_commission(db: Session, order: Order) -> EscrowLedger:
    balance = escrow_balance(db, order.id) - order.commission_amount
    return _append_entry(
        db, order.id, "commission", order.commission_amount, balance, "Platform commission deducted"
    )


def release_to_farmer(db: Session, order: Order) -> tuple[EscrowLedger, Wallet]:
    """Release escrow to farmer after delivery confirmation."""
    balance = escrow_balance(db, order.id) - order.farmer_net
    entry = _append_entry(db, order.id, "release", order.farmer_net, balance, "Release to farmer")
    wallet = _wallet(db, order.seller_id)
    wallet.version += 1
    wallet.balance = round(wallet.balance + order.farmer_net, 2)
    return entry, wallet


def refund_buyer(db: Session, order: Order) -> EscrowLedger:
    balance = escrow_balance(db, order.id) - order.total
    entry = _append_entry(db, order.id, "refund", order.total, balance, "Refund buyer on cancellation")
    wallet = _wallet(db, order.buyer_id)
    wallet.version += 1
    wallet.balance = round(wallet.balance + order.total, 2)
    return entry
