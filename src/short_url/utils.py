from datetime import datetime, timedelta, timezone
from typing import Optional

import asyncio
from sqlalchemy import delete, select, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import LINK_NO_USE_DAYS
from src.database import async_session_maker
from src.short_url.models import URL


async def perform_cleanup(session: Optional[AsyncSession] = None):
    now = datetime.now(timezone.utc)
    unused_threshold = now - timedelta(days=LINK_NO_USE_DAYS)
    query = delete(URL).where(
        or_(
            URL.expires_at < now,
            and_(
                or_(URL.last_watched_at < unused_threshold,
                    URL.last_watched_at.is_(None)
                    ),
                URL.created_at < unused_threshold
            )
        )
    )
    if session is None:
        async with async_session_maker() as session:
            await session.execute(query)
            await session.commit()
    else:
        await session.execute(query)
        await session.commit()


async def run_cleanup():
    while True:
        await perform_cleanup()
        await asyncio.sleep(600)


async def update_link_stats(short_url: str):
    async with async_session_maker() as session:
        query = select(URL).where(URL.short_url == short_url)
        result = await session.execute(query)
        link = result.scalar_one_or_none()
        if link:
            link.clicks_count += 1
            link.last_watched_at = datetime.now(timezone.utc)
            await session.commit()
