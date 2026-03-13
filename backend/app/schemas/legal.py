"""Pydantic schemas for Terms and Conditions."""

from pydantic import BaseModel, Field
from typing import Optional


class TermsPublicResponse(BaseModel):
    id: str
    title: str
    content: str
    version: int
    company_name: str
    updated_at: str


class TermsAcceptRequest(BaseModel):
    terms_id: str


class TermsAcceptResponse(BaseModel):
    message: str
    acceptance_id: str


class TermsCheckResponse(BaseModel):
    needs_acceptance: bool
    terms_id: Optional[str] = None
    version: Optional[int] = None
    title: Optional[str] = None


# ── Admin schemas ────────────────────────────────────

class AdminTermsListItem(BaseModel):
    id: str
    title: str
    version: int
    company_name: str
    is_active: bool
    created_at: str
    updated_at: str
    acceptance_count: int = 0


class AdminCreateTerms(BaseModel):
    title: str = Field(..., max_length=255)
    content: str
    version: int = Field(..., ge=1)
    company_name: str = Field(..., max_length=255)


class AdminUpdateTerms(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    content: Optional[str] = None
    company_name: Optional[str] = Field(None, max_length=255)
