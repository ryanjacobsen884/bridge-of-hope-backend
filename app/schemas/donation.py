from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class DonorPayload(BaseModel):
    email: EmailStr
    first_name: str = Field(min_length=1, max_length=120)
    last_name: str = Field(min_length=1, max_length=120)
    country_code: str = Field(min_length=2, max_length=2)
    phone: str | None = None


class OneOffCreate(BaseModel):
    provider: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    cover_fees: bool = False
    donor: DonorPayload
    consent: bool = False


class SubscriptionCreate(BaseModel):
    provider: str
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3)
    cover_fees: bool = False
    donor: DonorPayload
    consent: bool = False


class OneOffResponse(BaseModel):
    checkout_url: str | None = None
    client_secret: str | None = None
    mpesa_request_id: str | None = None
    provider_payment_id: str
    status: str


class SubscriptionResponse(BaseModel):
    checkout_url: str | None = None
    approval_url: str | None = None
    ratiba_request_id: str | None = None
    provider_subscription_id: str
    status: str


class ManageSubscriptionOut(BaseModel):
    id: str
    amount_minor: int
    currency: str
    status: str
    next_charge_at: str | None
    provider: str


class ManageSubscriptionPatch(BaseModel):
    amount_minor: int = Field(gt=0)
