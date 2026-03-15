import pytest
import pytest_asyncio
import redis.asyncio as redis
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool
from typing import AsyncGenerator

from src.config import TEST_DATABASE_URL
from src.database import get_async_session, get_redis
from src.main import app


@pytest_asyncio.fixture(scope="session")
async def engine_test():
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    yield engine


@pytest.fixture(scope="session")
async def async_session_maker(engine_test):
    maker = sessionmaker(engine_test,
                         class_=AsyncSession,
                         expire_on_commit=False)
    return maker


@pytest_asyncio.fixture
async def db_session(async_session_maker) -> AsyncGenerator[AsyncSession,
                                                            None]:
    async with async_session_maker() as session:
        yield session
        await session.execute(text("TRUNCATE TABLE urls CASCADE"))
        await session.execute(text('TRUNCATE TABLE "user" CASCADE'))
        await session.commit()


@pytest_asyncio.fixture(scope="function")
async def redis_client():
    client = redis.Redis(host='redis',
                         port=6379,
                         db=1,
                         decode_responses=True,
                         socket_connect_timeout=30,
                         socket_timeout=30)
    await client.ping()
    await client.flushdb()
    yield client
    await client.aclose()


@pytest_asyncio.fixture
async def ac(db_session, redis_client) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_async_session] = lambda: db_session
    app.dependency_overrides[get_redis] = lambda: redis_client

    async with AsyncClient(transport=ASGITransport(app=app),
                           base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_headers(ac: AsyncClient) -> dict:
    import uuid

    email = f"user_{uuid.uuid4()}@example.com"
    password = "string"

    resp_reg = await ac.post("/auth/register", json={
        "email": email, "password": password, "username": "user"
    })
    assert resp_reg.status_code in (200, 201)

    resp_login = await ac.post("/auth/jwt/login", data={
        "username": email, "password": password
    })
    assert resp_login.status_code == 200

    token = resp_login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
