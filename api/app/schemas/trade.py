from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrderCreate(BaseModel):
    listing_id: int
    quantity: float = Field(gt=0)
    delivery_notes: str | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    buyer_id: int
    listing_id: int
    seller_id: int
    quantity: float
    unit_price: float
    total: float
    currency: str
    commission_rate: float
    commission_amount: float
    farmer_net: float
    status: str
    delivery_notes: str | None
    delivery_proof_url: str | None
    created_at: datetime
    settled_at: datetime | None


class ConfirmDeliveryRequest(BaseModel):
    proof_url: str | None = None
    note: str | None = None


class LedgerEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    entry_type: str
    amount: float
    balance_after: float
    reference: str
    sha256_hash: str
    note: str | None
    created_at: datetime
