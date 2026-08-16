# Farm-to-Fork — by NOVARA

A farm-to-fork PWA connecting coffee and agri-food producers directly with consumers — with biosensor food-safety telemetry, AI plant diagnostics, localized voice assistance, escrow payments, and market intelligence.

## Stack

| Layer | Tech |
|-------|------|
| Frontend | Next.js 15 (App Router), React 19, Tailwind CSS v4, Zustand |
| Backend | FastAPI (Python 3.13), SQLAlchemy, Pydantic v2 |
| Database | PostgreSQL / PostGIS (SQLite for dev + tests) |
| App shell | PWA — installable, offline-first with background sync |

## Features

- **Direct marketplace** — farmers list crops (coffee, grains, produce, livestock) with location-aware sorting and region/category filters.
- **Escrow payments** — SHA-256 chained ledger, 2.5% platform commission, transparent wallet balance per order.
- **Biosensor telemetry** — multi-threat screening (mycotoxins, pesticide residues, moisture) with risk gauges and simulator for Phase-1.
- **AI diagnostics** — upload a leaf photo, get plant-disease analysis (OpenAI/Anthropic vision or mock).
- **Voice agent** — record in your language; Whisper transcription + localized replies (English, Luganda, Swahili, Acholi, Runyankore).
- **Market intelligence** — price forecasts and crop recommendations.
- **Security** — bcrypt, JWT access/refresh, TOTP 2FA, AES-256-GCM field encryption, rate limiting, input validation.

## Getting started

### 1. Backend

```bash
python -m venv .venv
.\.venv\Scripts\activate            # Windows (PowerShell)
pip install -r api/requirements.txt
python -m api.app.scripts.seed      # optional seed data
python -m uvicorn api.app.main:app --reload --port 8000 --app-dir .
```

Set `DATABASE_URL` and `SECRET_KEY` (see `.env.example`). SQLite dev DB is used by default.

### 2. Frontend

```bash
pnpm install
pnpm --filter @farm/web dev        # http://localhost:3000
```

Point `NEXT_PUBLIC_API_URL` at the API (default `http://localhost:8000`).

### 3. Tests

```bash
pytest api/tests -q                # backend
pnpm --filter @farm/web build      # typecheck + lint + build
```

## Seed accounts

| Role | Email | Password |
|------|-------|----------|
| Farmer | `grace@novara.ug` | `Farmer!Pass1` |
| Consumer | `daniel@novara.ug` | `Buyer!Pass1` |
| Admin | `admin@novara.ug` | `Admin!Pass1` |

## CI

`.github/workflows/ci.yml` runs backend tests and the frontend build on every push/PR to `main`.
