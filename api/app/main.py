import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.app.config import settings
from api.app.database import init_db
from api.app.routers import (
    admin,
    auth,
    biosensor,
    diagnostics,
    escrow,
    listings,
    market,
    orders,
    users,
    voice,
    webhooks,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    description="Farm-to-fork API: direct farmer-consumer marketplace with biosensor "
    "tracking, vision diagnostics, localized voice agents and escrow commissions.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Permissions-Policy"] = "geolocation=(self), microphone=(self)"
    response.headers["X-Request-Time-Ms"] = f"{int((time.perf_counter() - start) * 1000)}"
    return response


@app.get("/")
def root():
    return {"service": settings.app_name, "status": "ok", "docs": "/docs"}


@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": time.time()}


for router in (
    auth.router,
    users.router,
    listings.router,
    orders.router,
    escrow.router,
    biosensor.router,
    diagnostics.router,
    voice.router,
    market.router,
    webhooks.router,
    admin.router,
):
    app.include_router(router, prefix=settings.api_prefix)

os.makedirs(settings.upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
