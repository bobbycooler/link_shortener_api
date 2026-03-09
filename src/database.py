from fastapi import Depends
from fastapi_users.db import SQLAlchemyUserDatabase
import redis.asyncio as redis
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL, REDIS_URL


Base = declarative_base()

engine = create_async_engine(DATABASE_URL)
async_session_maker = sessionmaker(engine,
                                   class_=AsyncSession,
                                   expire_on_commit=False)


async def get_async_session():
    async with async_session_maker() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    from auth.models import User
    yield SQLAlchemyUserDatabase(session, User)


pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)


async def get_redis():
    client = redis.Redis(connection_pool=pool)
    try:
        yield client
    finally:
        await client.close()
