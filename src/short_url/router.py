from datetime import datetime, timezone
from typing import Optional, List
from secrets import token_urlsafe

from fastapi import (APIRouter,
                     Depends,
                     HTTPException,
                     status,
                     BackgroundTasks,
                     Query)
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete, select
from pydantic import HttpUrl
from redis.asyncio import Redis

from database import get_async_session, get_redis
from auth.models import User
from auth.users import current_active_user, current_user_optional
from short_url.models import URL
from short_url.schemas import URLCreate, URLRead, URLUpdate
from short_url.utils import update_link_stats

links_router = APIRouter()


@links_router.get("/search", response_model=List[URLRead])
async def search_by_original_url(
    original_url: HttpUrl,
    db: AsyncSession = Depends(get_async_session)
):
    query = select(URL).where(URL.long_url == str(original_url))
    result = await db.execute(query)
    links = result.scalars().all()

    if not links:
        raise HTTPException(
            status_code=404,
            detail="Для этого URL нет коротких ссылок"
        )

    return links


@links_router.get("/my", response_model=List[URLRead])
async def get_my_links(
    limit: int = Query(10, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)
):
    query = (
        select(URL)
        .where(URL.author_id == user.id)
        .order_by(URL.created_at.desc())
        .limit(limit)
        .offset(offset)
    )

    result = await db.execute(query)
    links = result.scalars().all()

    return links


@links_router.post("/shorten",
                   response_model=URLRead,
                   status_code=status.HTTP_201_CREATED)
async def shorten_url(
    url_data: URLCreate,
    db: AsyncSession = Depends(get_async_session),
    user: Optional[User] = Depends(current_user_optional),
    redis: Redis = Depends(get_redis)
):
    if url_data.expires_at:
        user_expires_at = url_data.expires_at
        if user_expires_at.tzinfo is None:
            user_expires_at = user_expires_at.replace(tzinfo=timezone.utc)
        else:
            user_expires_at = user_expires_at.astimezone(timezone.utc)

        if user_expires_at <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Время истечения ссылки не может быть в прошлом"
            )
    else:
        user_expires_at = None

    if url_data.custom_alias:
        query = select(URL).where(URL.short_url == url_data.custom_alias)
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400,
                                detail="Этот custom_alias уже занят")
        short_url = url_data.custom_alias
    else:
        short_url = token_urlsafe(6)

    new_link = URL(
        long_url=str(url_data.long_url),
        short_url=short_url,
        author_id=user.id if user else None,
        expires_at=user_expires_at
    )
    db.add(new_link)
    await db.commit()
    await db.refresh(new_link)

    redis_ttl = 3600
    if new_link.expires_at:
        expire_date = new_link.expires_at.replace(tzinfo=timezone.utc)
        remaining = int(
            (expire_date - datetime.now(timezone.utc)).total_seconds()
        )
        redis_ttl = min(3600, remaining)
    await redis.set(f"url:{new_link.short_url}",
                    new_link.long_url,
                    ex=redis_ttl)

    return new_link


@links_router.get("/{short_code}")
async def redirect_to_url(
    short_code: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_session),
    redis: Redis = Depends(get_redis)
):
    cached_url = await redis.get(f"url:{short_code}")
    if cached_url:
        background_tasks.add_task(update_link_stats, short_url=short_code)
        return RedirectResponse(url=cached_url)

    query = select(URL).where(URL.short_url == short_code)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    now = datetime.now(timezone.utc)
    if link.expires_at and now > link.expires_at.replace(tzinfo=timezone.utc):
        await db.delete(link)
        await db.commit()
        raise HTTPException(status_code=410,
                            detail="Срок действия ссылки истек")

    redis_ttl = 3600
    if link.expires_at:
        expire_date = link.expires_at.replace(tzinfo=timezone.utc)
        remaining = int(
            (expire_date - datetime.now(timezone.utc)).total_seconds()
        )
        redis_ttl = min(3600, remaining)
    await redis.set(f"url:{short_code}",
                    link.long_url,
                    ex=redis_ttl)

    link.clicks_count += 1
    link.last_watched_at = datetime.now(timezone.utc)

    await db.commit()
    return RedirectResponse(url=link.long_url)


@links_router.delete("/{short_code}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    short_code: str,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    redis: Redis = Depends(get_redis)
):
    query = delete(URL).where(URL.short_url == short_code,
                              URL.author_id == user.id)
    result = await db.execute(query)

    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    await db.commit()
    await redis.delete(f"url:{short_code}")
    return None


@links_router.put("/{short_code}", response_model=URLRead)
async def update_link(
    short_code: str,
    update_data: URLUpdate,
    db: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user),
    redis: Redis = Depends(get_redis)
):
    query = select(URL).where(URL.short_url == short_code,
                              URL.author_id == user.id)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404,
                            detail="Ссылка не найдена")

    if update_data.new_short_code != short_code:
        check_query = select(URL).where(
            URL.short_url == update_data.new_short_code)
        check_result = await db.execute(check_query)
        if check_result.scalar_one_or_none():
            raise HTTPException(status_code=400,
                                detail="Этот короткий код уже занят")

    old_short_code = link.short_url
    link.short_url = update_data.new_short_code
    await db.commit()
    await db.refresh(link)
    await redis.delete(f"url:{old_short_code}")
    return link


@links_router.get("/{short_code}/stats", response_model=URLRead)
async def get_link_stats(
    short_code: str,
    db: AsyncSession = Depends(get_async_session)
):
    query = select(URL).where(URL.short_url == short_code)
    result = await db.execute(query)
    link = result.scalar_one_or_none()

    if not link:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")
    return link
