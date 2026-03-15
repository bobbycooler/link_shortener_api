from datetime import datetime, timedelta, timezone

import asyncio
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.short_url.models import URL
from src.short_url.utils import perform_cleanup


@pytest.mark.asyncio
async def test_shorten_url_anonymous(ac, redis_client):
    payload = {"long_url": "https://example.com/"}
    response = await ac.post("links/shorten", json=payload)

    assert response.status_code == 201
    data = response.json()
    assert "short_url" in data
    assert data["author_id"] is None

    cached = await redis_client.get(f"url:{data['short_url']}")
    assert cached == "https://example.com/"


@pytest.mark.asyncio
async def test_shorten_url_authenticated(ac, auth_headers):
    payload = {
        "long_url": "https://example.ru",
        "custom_alias": "alias"
    }
    response = await ac.post("links/shorten",
                             json=payload,
                             headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["short_url"] == "alias"
    assert data["author_id"] is not None


@pytest.mark.asyncio
async def test_shorten_url_duplicate_alias(ac,
                                           auth_headers):
    payload = {
        "long_url": "https://example.ru",
        "custom_alias": "unique_alias"
    }

    response = await ac.post("links/shorten",
                             json=payload,
                             headers=auth_headers)
    assert response.status_code == 201
    assert response.json()["short_url"] == "unique_alias"

    duplicate_payload = {
        "long_url": "https://site.com",
        "custom_alias": "unique_alias"
    }
    dup_response = await ac.post("links/shorten",
                                 json=duplicate_payload,
                                 headers=auth_headers)

    assert dup_response.status_code == 400
    assert dup_response.json()["detail"] == "Этот custom_alias уже занят"


@pytest.mark.asyncio
async def test_redirect_and_stats_update(ac):
    create_res = await ac.post("links/shorten",
                               json={"long_url": "https://yandex.ru/"})
    short_code = create_res.json()["short_url"]

    redirect_res = await ac.get(f"links/{short_code}", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://yandex.ru/"

    await asyncio.sleep(0.1)
    stats_res = await ac.get(f"links/{short_code}/stats")
    assert stats_res.json()["clicks_count"] == 1
    assert stats_res.json()["last_watched_at"] is not None


@pytest.mark.asyncio
async def test_redirect_404(ac: AsyncClient):
    random_code = "non_existent_12345"
    response = await ac.get(f"links/{random_code}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Ссылка не найдена"


@pytest.mark.asyncio
async def test_redirect_db_fallback(ac, redis_client):
    res = await ac.post("links/shorten", json={"long_url": "https://test.com"})
    code = res.json()["short_url"]

    await redis_client.delete(f"url:{code}")

    response = await ac.get(f"links/{code}", follow_redirects=False)
    assert response.status_code == 307
    assert await redis_client.get(f"url:{code}") is not None


@pytest.mark.asyncio
async def test_get_link_stats_not_found(ac):
    random_code = "non_existent_12345"

    response = await ac.get(f"links/{random_code}/stats")

    assert response.status_code == 404
    assert response.json()["detail"] == "Ссылка не найдена"


@pytest.mark.asyncio
async def test_redirect_expired_link_returns_410(ac,
                                                 db_session,
                                                 redis_client):
    await redis_client.delete("url:expired_now")
    session = db_session
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    expired_link = URL(
        long_url="https://old.com",
        short_url="expired_now",
        expires_at=past_time
    )
    session.add(expired_link)
    await session.commit()

    response = await ac.get("links/expired_now", follow_redirects=False)

    assert response.status_code == 410
    assert response.json()["detail"] == "Срок действия ссылки истек"

    query = select(URL).where(URL.short_url == "expired_now")
    result = await session.execute(query)
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_search_by_url_both_scenarios(ac):
    long_url = "https://test.ru"
    response = await ac.get("links/search", params={"original_url": long_url})
    assert response.status_code == 404

    await ac.post("links/shorten", json={"long_url": long_url})
    response = await ac.get("links/search", params={"original_url": long_url})
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_get_my_links(ac, auth_headers):
    await ac.post("links/shorten",
                  json={"long_url": "https://example.com"},
                  headers=auth_headers)

    response = await ac.get("links/my", headers=auth_headers)
    assert response.status_code == 200
    assert len(response.json()) > 0


@pytest.mark.asyncio
async def test_get_my_links_empty(ac):
    new_user_email = "new_user@test.com"
    await ac.post("/auth/register", json={
        "email": new_user_email,
        "password": "string",
        "username": "new_user"
    })
    login_res = await ac.post("/auth/jwt/login", data={
        "username": new_user_email,
        "password": "string"
    })
    new_user_token = login_res.json()["access_token"]
    new_user_headers = {"Authorization": f"Bearer {new_user_token}"}

    response = await ac.get("links/my", headers=new_user_headers)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_update_link_code(ac,
                                auth_headers,
                                redis_client):
    long_url = "https://example.com"
    res = await ac.post("links/shorten",
                        json={"long_url": long_url},
                        headers=auth_headers)
    old_code = res.json()["short_url"]

    new_code = "new_shorten"
    update_res = await ac.put(f"links/{old_code}",
                              json={"long_url": long_url,
                                    "new_short_code": new_code},
                              headers=auth_headers)

    assert update_res.status_code == 200
    assert update_res.json()["short_url"] == new_code
    assert await redis_client.get(f"url:{old_code}") is None


@pytest.mark.asyncio
async def test_update_link_not_found(ac, auth_headers):
    response = await ac.put(
        "links/non_existent_code",
        json={"long_url": "https://example.com",
              "new_short_code": "some_new_code"},
        headers=auth_headers
    )
    assert response.status_code == 404
    assert response.json()["detail"] == "Ссылка не найдена"


@pytest.mark.asyncio
async def test_update_link_alias_taken(ac, auth_headers):
    long_url1 = "https://example.com"
    long_url2 = "https://example2.com"
    await ac.post("links/shorten",
                  json={"long_url": long_url1,
                        "custom_alias": "code1"},
                  headers=auth_headers)
    await ac.post("links/shorten",
                  json={"long_url": long_url2,
                        "custom_alias": "code2"},
                  headers=auth_headers)

    response = await ac.put(
        "links/code1",
        json={"long_url": long_url1,
              "new_short_code": "code2"},
        headers=auth_headers
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Этот короткий код уже занят"


@pytest.mark.asyncio
async def test_expired_link_decline(ac):
    past_time = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    res = await ac.post("links/shorten", json={
        "long_url": "https://example_expired.com",
        "expires_at": past_time
    })
    error_string = "Время истечения ссылки не может быть в прошлом"
    assert res.status_code == 400
    assert res.json()["detail"] == error_string


@pytest.mark.asyncio
async def test_delete_link(ac, auth_headers, redis_client):
    res = await ac.post("links/shorten",
                        json={"long_url": "https://example2delete.com"},
                        headers=auth_headers)
    short_code = res.json()["short_url"]

    del_res = await ac.delete(f"links/{short_code}", headers=auth_headers)
    assert del_res.status_code == 204

    assert await redis_client.get(f"url:{short_code}") is None
    check_res = await ac.get(f"links/{short_code}")
    assert check_res.status_code == 404


@pytest.mark.asyncio
async def test_forbidden_delete_other_user_link(ac,
                                                auth_headers):
    res = await ac.post("links/shorten",
                        json={"long_url": "https://example.com",
                              "custom_alias": "test_delete"},
                        headers=auth_headers)
    assert res.status_code in (200, 201)
    short_code = res.json()['short_url']

    second_user_email = "second_user@test.com"
    await ac.post("/auth/register", json={
        "email": second_user_email,
        "password": "string",
        "username": "second_user"
    })
    login_res = await ac.post("/auth/jwt/login", data={
        "username": second_user_email,
        "password": "string"
    })
    second_user_token = login_res.json()["access_token"]
    second_user_headers = {"Authorization": f"Bearer {second_user_token}"}

    del_res = await ac.delete(f"links/{short_code}",
                              headers=second_user_headers)

    assert del_res.status_code == 404


@pytest.mark.asyncio
async def test_forbidden_update_other_user_link(ac,
                                                auth_headers):
    res = await ac.post("links/shorten",
                        json={"long_url": "https://example.com",
                              "custom_alias": "test_change"},
                        headers=auth_headers)
    short_code = res.json()['short_url']
    long_url = res.json()['long_url']

    second_user_email = "second_user2@test.com"
    await ac.post("/auth/register", json={
        "email": second_user_email,
        "password": "string",
        "username": "second_user2"
    })
    login_res = await ac.post("/auth/jwt/login", data={
        "username": second_user_email,
        "password": "string"
    })
    second_user_token = login_res.json()["access_token"]
    second_user_headers = {"Authorization": f"Bearer {second_user_token}"}

    update_res = await ac.put(f"links/{short_code}",
                              json={"long_url": long_url,
                                    "new_short_code": "second_user_change"},
                              headers=second_user_headers)

    assert update_res.status_code == 404


@pytest.mark.asyncio
async def test_anonymous_cannot_delete_link(ac):
    response = await ac.delete("links/some_alias")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anonymous_cannot_update_link(ac):
    response = await ac.put("links/some_alias",
                            json={"new_short_code": "anonym_change"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_anonymous_cannot_see_my_links(ac):
    response = await ac.get("links/my")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_shorten_invalid_url(ac):
    response = await ac.post("links/shorten",
                             json={"long_url": "not-valid-url"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "long_url"]


@pytest.mark.asyncio
async def test_search_invalid_url(ac):
    response = await ac.get("links/search",
                            params={"original_url": "not-valid-url"})

    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["query", "original_url"]


@pytest.mark.asyncio
async def test_cleanup_removes_expired_and_old_links(db_session):
    session = db_session
    now = datetime.now(timezone.utc)
    links = [
        URL(short_url="exp",
            long_url="http://test.com",
            expires_at=now-timedelta(hours=1)),
        URL(short_url="old",
            long_url="http://test.com",
            created_at=now-timedelta(days=40),
            last_watched_at=None),
        URL(short_url="live",
            long_url="http://test.com",
            created_at=now)
    ]
    session.add_all(links)
    await session.commit()

    await perform_cleanup(session=session)

    res = await session.execute(select(URL))
    remaining = res.scalars().all()

    assert len(remaining) == 1
    assert remaining[0].short_url == "live"
