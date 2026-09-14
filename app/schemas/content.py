from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, EmailStr


class PostOut(BaseModel):
    slug: str
    title: str
    excerpt: str
    cover_image_url: str | None
    published_at: datetime | None

    model_config = {"from_attributes": True}


class PostDetailOut(PostOut):
    body_md: str


class NewsletterSubscribe(BaseModel):
    email: EmailStr


class DataRequestCreate(BaseModel):
    email: EmailStr
    type: str
    notes: str | None = None
