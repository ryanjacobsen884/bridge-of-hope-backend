import asyncio
import sys

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import get_settings
from app.db import _to_asyncpg_url
from app.main import app

if sys.platform == "win32":
    # asyncpg's cancel/cleanup path is flaky under Windows' default
    # ProactorEventLoop (it can tear down the loop mid-cleanup). The
    # selector loop is the documented workaround.
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db_session():
    """A DB engine/session scoped to *this test's* event loop.

    The app's module-level engine (app.db.engine) is a singleton created at
    import time; reusing it across pytest-asyncio's per-test event loops
    causes asyncpg connections to end up "attached to a different loop".
    Tests that need the database get their own short-lived engine instead.
    """
    settings = get_settings()
    engine = create_async_engine(_to_asyncpg_url(settings.database_url), pool_pre_ping=True)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()
