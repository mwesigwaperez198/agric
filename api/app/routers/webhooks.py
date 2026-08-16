from fastapi import APIRouter, HTTPException

from api.app.deps import CurrentUser, DbSession
from api.app.services.payments import log_webhook

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/webhook")
async def payment_webhook(payload: dict, provider: str = "mobile_money"):
    """Phase 1 isolated webhook: logs provider notifications to a JSONL file."""
    if not payload:
        raise HTTPException(status_code=400, detail="Empty webhook payload")
    event = payload.get("event") or payload.get("status") or "notification"
    record_id = log_webhook(provider, event, payload)
    return {"accepted": True, "webhook_log_id": record_id}


@router.get("/webhook-log")
def webhook_log(user: CurrentUser, db: DbSession, limit: int = 20):
    """Admin-only view of the persisted webhook log."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    lines = []
    try:
        with open("data/webhooks.jsonl", encoding="utf-8") as fh:
            lines = [line for line in fh if line.strip()][-limit:]
    except FileNotFoundError:
        pass
    return {"records": lines}
