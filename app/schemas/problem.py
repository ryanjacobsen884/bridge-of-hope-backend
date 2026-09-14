"""RFC 7807 problem-detail JSON."""
from __future__ import annotations

from pydantic import BaseModel


class ProblemDetail(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
