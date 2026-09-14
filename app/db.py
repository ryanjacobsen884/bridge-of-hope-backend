"""Async SQLAlchemy engine/session setup.

Neon scales to zero, so cold starts happen. We retry connection with backoff
rather than fail the first request after idle.
"""
from __future__ import annotations

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings

log = logging.getLogger("bridgeofhope.db")

settings = get_settings()

# The `neon` CLI rewrites .env's DATABASE_URL to a plain libpq-style URL
# (postgresql://..., sslmode=require&channel_binding=require) on every
# `neon link` / `neon deploy`. asyncpg wants the postgresql+asyncpg:// driver
# and doesn't understand sslmode/channel_binding as connect kwargs, so we
# normalize whatever shape shows up in the env rather than hand-editing .env
# every time the CLI touches it.
def _to_asyncpg_url(url: str) -> str:
    parts = urlsplit(url)
    scheme = "postgresql+asyncpg"
    query = dict(parse_qsl(parts.query))
    query.pop("channel_binding", None)
    if query.pop("sslmode", None) or "ssl" not in query:
        query.setdefault("ssl", "require")
    new_query = urlencode(query)
    return urlunsplit((scheme, parts.netloc, parts.path, new_query, parts.fragment))


engine = create_async_engine(
    _to_asyncpg_url(settings.database_url),
    pool_pre_ping=True,
    pool_recycle=300,
    connect_args={"server_settings": {"application_name": "bridgeofhope-backend"}},
)

SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@retry(
    reraise=True,
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=8),
    retry=retry_if_exception_type(Exception),
)
async def connect_with_retry() -> None:
    """Ping the DB with backoff — covers Neon cold-start on scale-to-zero."""
    async with engine.connect() as conn:
        await conn.exec_driver_sql("SELECT 1")


async def get_db():
    async with SessionLocal() as session:
        yield session
