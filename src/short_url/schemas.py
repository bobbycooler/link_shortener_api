from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from datetime import datetime
from typing import Optional


class URLBase(BaseModel):
    long_url: HttpUrl


class URLCreate(URLBase):
    custom_alias: Optional[str] = Field(None)
    expires_at: Optional[datetime] = None


class URLRead(URLBase):
    id: int
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    clicks_count: int
    last_watched_at: Optional[datetime] = None
    author_id: Optional[int] = None

    model_config = ConfigDict(from_attributes=True)


class URLUpdate(URLBase):
    new_short_code: str = Field(None)


class URLSearchResponse(BaseModel):
    short_url: str
    long_url: HttpUrl
    full_short_url: str
