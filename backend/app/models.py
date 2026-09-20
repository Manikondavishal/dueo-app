"""Pydantic v2 request/response schemas."""
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from .util import norm_email

BUSINESS_TYPES = ["agency_studio", "consulting", "it_software", "other"]
AUTO_REVIEW_TYPES = {"agency_studio", "consulting", "it_software"}


class InviteRequestIn(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    business_name: str = Field(min_length=1, max_length=160)
    work_email: str
    mobile: str = Field(min_length=1, max_length=20)
    business_type: str
    city_state: str = Field(default="", max_length=160)
    monthly_invoice_volume: str = Field(default="", max_length=40)
    udyam_number: Optional[str] = Field(default=None, max_length=40)
    # Honeypot — must stay empty for real humans.
    company_website: str = Field(default="")

    @field_validator("work_email")
    @classmethod
    def _email(cls, v: str) -> str:
        return norm_email(v)

    @field_validator("business_type")
    @classmethod
    def _btype(cls, v: str) -> str:
        return v if v in BUSINESS_TYPES else "other"


class EmailIn(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return norm_email(v)


class VerifyIn(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return norm_email(v)


class SetupIn(BaseModel):
    display_name: str = Field(min_length=1, max_length=160)
    mobile: str = Field(min_length=1, max_length=20)
    udyam_number: Optional[str] = Field(default=None, max_length=40)
    consent: bool = False
    consent_version: str = "2026-06-01"


class LeadActionIn(BaseModel):
    action: str  # approve | hold | reject
    note: str = Field(default="", max_length=500)
