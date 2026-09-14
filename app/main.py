from __future__ import annotations

import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.db import connect_with_retry
from app.routers import admin, content, donations, subscriptions, webhooks

logging.basicConfig(level=get_settings().log_level)
log = logging.getLogger("bridgeofhope")

settings = get_settings()

app = FastAPI(title="The Bridge of Hope Foundation API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def on_startup() -> None:
    # Neon scales to zero; retry with backoff instead of failing the first request.
    await connect_with_retry()
    log.info("Database reachable. Environment=%s", settings.environment)


def _problem(status: int, title: str, detail: str | None = None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"type": "about:blank", "title": title, "status": status, "detail": detail},
        media_type="application/problem+json",
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    # Never leak provider error text or stack traces to the client.
    return _problem(exc.status_code, title=exc.detail if isinstance(exc.detail, str) else "Error", detail=None)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _problem(422, title="Validation error", detail="One or more fields were invalid.")


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _problem(500, title="Internal server error")


app.include_router(content.router)
app.include_router(donations.router)
app.include_router(subscriptions.router)
app.include_router(webhooks.router)
app.include_router(admin.router)
