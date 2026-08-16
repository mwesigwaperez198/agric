def _create_ready_order(client, auth_headers, consumer_headers):
    client.post(
        "/api/v1/farms",
        headers=auth_headers,
        json={"name": "Test Farm", "region": "Kampala", "latitude": 0.3, "longitude": 32.5},
    )
    r = client.post(
        "/api/v1/listings",
        headers=auth_headers,
        json={
            "crop_name": "Arabica Coffee",
            "category": "coffee",
            "quantity": 100,
            "unit": "kg",
            "price_per_unit": 10000,
            "region": "Kampala",
            "latitude": 0.3,
            "longitude": 32.5,
        },
    )
    listing = r.json()
    r = client.post(
        "/api/v1/orders",
        headers=consumer_headers,
        json={"listing_id": listing["id"], "quantity": 10},
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_order_escrow_flow(client, auth_headers, consumer_headers):
    order = _create_ready_order(client, auth_headers, consumer_headers)
    assert order["status"] == "in_escrow"
    assert order["total"] == 100000
    assert order["commission_amount"] == 2500  # 2.5%
    assert order["farmer_net"] == 97500

    ledger = client.get(f"/api/v1/orders/{order['id']}/ledger", headers=consumer_headers)
    assert ledger.status_code == 200
    entries = ledger.json()
    assert [e["entry_type"] for e in entries] == ["deposit"]
    hashes = [e["sha256_hash"] for e in entries]
    assert len(set(hashes)) == len(hashes)

    balance = client.get(f"/api/v1/orders/{order['id']}/balance", headers=consumer_headers).json()
    assert balance["escrow_balance"] == 100000.0

    # Confirm delivery settles and credits farmer wallet.
    r = client.post(
        f"/api/v1/orders/{order['id']}/confirm",
        headers=consumer_headers,
        json={"proof_url": "https://cdn/photo-1.jpg", "note": "Delivered at gate"},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "settled"

    ledger = client.get(f"/api/v1/orders/{order['id']}/ledger", headers=consumer_headers).json()
    assert [e["entry_type"] for e in ledger] == ["deposit", "commission", "release"]
    balance = client.get(f"/api/v1/orders/{order['id']}/balance", headers=consumer_headers).json()
    assert balance["escrow_balance"] == 0.0

    wallet = client.get("/api/v1/me/wallet", headers=auth_headers)
    assert wallet.json()["balance"] == 97500


def test_order_cancel_refunds(client, auth_headers, consumer_headers):
    order = _create_ready_order(client, auth_headers, consumer_headers)
    r = client.post(f"/api/v1/orders/{order['id']}/cancel", headers=consumer_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "cancelled"


def test_admin_ledger_verification(client, auth_headers, consumer_headers, admin_headers):
    order = _create_ready_order(client, auth_headers, consumer_headers)
    client.post(f"/api/v1/orders/{order['id']}/confirm", headers=consumer_headers)

    # non-admins are rejected
    r = client.get(f"/api/v1/admin/ledger/verify/{order['id']}", headers=consumer_headers)
    assert r.status_code == 403

    # admins can recompute and confirm the chain is intact
    r = client.get(f"/api/v1/admin/ledger/verify/{order['id']}", headers=admin_headers)
    assert r.status_code == 200, r.text
    assert r.json()["verified"] is True
    assert len(r.json()["tail_hash"]) == 64

    # tampering with an entry breaks the chain at that entry
    from api.app.database import SessionLocal
    from api.app.models.trade import EscrowLedger

    db = SessionLocal()
    row = db.query(EscrowLedger).filter(EscrowLedger.order_id == order["id"]).order_by(EscrowLedger.id.asc()).first()
    row.amount = row.amount + 1
    db.commit()
    db.close()
    r = client.get(f"/api/v1/admin/ledger/verify/{order['id']}", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["verified"] is False
    assert r.json()["broken_at"] is not None


def test_webhook_logging(client, auth_headers):
    r = client.post(
        "/api/v1/payments/webhook",
        headers=auth_headers,
        json={"event": "charge.success", "amount": 1000, "reference": "ord-1"},
    )
    assert r.status_code == 200
    assert r.json()["accepted"] is True
