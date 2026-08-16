def test_diagnostics_guardrail(client, auth_headers):
    r = client.post(
        "/api/v1/voice/query",
        headers=auth_headers,
        json={"text": "Who should I vote for in the next election?", "locale": "en"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["guardrail"] is False
    assert "only answers questions about farming" in body["answer"]


def test_diagnostics_agri_question(client, auth_headers):
    r = client.post(
        "/api/v1/voice/query",
        headers=auth_headers,
        json={"text": "How do I treat coffee leaf rust?", "locale": "en"},
    )
    assert r.status_code == 200
    assert r.json()["guardrail"] is True
    assert "rust" in r.json()["answer"].lower()


def test_diagnostics_dialect_translation(client, auth_headers):
    r = client.post(
        "/api/v1/voice/query",
        headers=auth_headers,
        json={"text": "What is the price of maize this week?", "locale": "sw"},
    )
    body = r.json()
    assert body["guardrail"] is True
    assert body["dialect"] == "sw"


def test_image_analysis_mock(client, auth_headers):
    import struct
    import zlib

    # Build a minimal valid PNG.
    def chunk(tag: bytes, data: bytes) -> bytes:
        c = tag + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = b"\x00\xff\x00\x00"
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    r = client.post(
        "/api/v1/diagnostics/analyze",
        headers=auth_headers,
        files={"file": ("leaf.png", png, "image/png")},
        data={"crop_type": "coffee"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["guardrail_passed"] is True
    assert "confidence" in body["prediction"]
    assert body["model"] == "mock-cnn"


def test_image_rejects_non_image(client, auth_headers):
    r = client.post(
        "/api/v1/diagnostics/analyze",
        headers=auth_headers,
        files={"file": ("evil.txt", b"not an image at all", "text/plain")},
        data={"crop_type": "coffee"},
    )
    assert r.status_code == 400
