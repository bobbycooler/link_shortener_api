from datetime import datetime, timedelta, timezone

import asyncio
from sqlalchemy import delete, select, or_, and_

from config import LINK_NO_USE_DAYS
from database import async_session_maker
from short_url.models import URL


async def run_cleanup():
    while True:
        async with async_session_maker() as session:
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
            await session.execute(query)
            await session.commit()
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
