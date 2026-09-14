"""Signed, expiring, single-purpose manage-tokens for the donor self-service page.

No login: possession of the link (sent in every receipt) is the credential.
Token embeds the donor id; itsdangerous handles signing + expiry.
"""
from __future__ import annotations

import uuid

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

MANAGE_TOKEN_MAX_AGE = 60 * 60 * 24 * 90  # 90 days


def _serializer(secret_key: str) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(secret_key, salt="donor-manage-token")


def issue_manage_token(secret_key: str, donor_id: uuid.UUID) -> str:
    return _serializer(secret_key).dumps({"donor_id": str(donor_id)})


def verify_manage_token(secret_key: str, token: str) -> uuid.UUID | None:
    try:
        data = _serializer(secret_key).loads(token, max_age=MANAGE_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired):
        return None
    try:
        return uuid.UUID(data["donor_id"])
    except (KeyError, ValueError, TypeError):
        return None
