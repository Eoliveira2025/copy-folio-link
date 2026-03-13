"""Public legal endpoints for Terms and Conditions."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.terms import TermsDocument, TermsAcceptance
from app.models.user import User
from app.schemas.legal import TermsPublicResponse, TermsAcceptRequest, TermsAcceptResponse, TermsCheckResponse

router = APIRouter()


@router.get("/terms", response_model=TermsPublicResponse)
async def get_active_terms(db: AsyncSession = Depends(get_db)):
    """Return the currently active Terms and Conditions."""
    result = await db.execute(
        select(TermsDocument).where(TermsDocument.is_active == True)
    )
    terms = result.scalar_one_or_none()
    if not terms:
        raise HTTPException(status_code=404, detail="No active terms found")

    return TermsPublicResponse(
        id=str(terms.id),
        title=terms.title,
        content=terms.content,
        version=terms.version,
        company_name=terms.company_name,
        updated_at=terms.updated_at.isoformat(),
    )


@router.post("/terms/accept", response_model=TermsAcceptResponse)
async def accept_terms(
    body: TermsAcceptRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Record user acceptance of Terms and Conditions."""
    result = await db.execute(
        select(TermsDocument).where(TermsDocument.id == body.terms_id)
    )
    terms = result.scalar_one_or_none()
    if not terms:
        raise HTTPException(status_code=404, detail="Terms document not found")

    # Check if already accepted this version
    existing = await db.execute(
        select(TermsAcceptance).where(
            TermsAcceptance.user_id == user.id,
            TermsAcceptance.terms_id == terms.id,
        )
    )
    if existing.scalar_one_or_none():
        return TermsAcceptResponse(message="Already accepted", acceptance_id="existing")

    acceptance = TermsAcceptance(
        user_id=user.id,
        terms_id=terms.id,
        version=terms.version,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent", "")[:500],
    )
    db.add(acceptance)
    await db.commit()
    await db.refresh(acceptance)

    return TermsAcceptResponse(
        message="Terms accepted successfully",
        acceptance_id=str(acceptance.id),
    )


@router.get("/terms/check", response_model=TermsCheckResponse)
async def check_terms_acceptance(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Check if user needs to accept new terms."""
    result = await db.execute(
        select(TermsDocument).where(TermsDocument.is_active == True)
    )
    terms = result.scalar_one_or_none()
    if not terms:
        return TermsCheckResponse(needs_acceptance=False)

    # Check if user accepted this specific active terms version
    acceptance = await db.execute(
        select(TermsAcceptance).where(
            TermsAcceptance.user_id == user.id,
            TermsAcceptance.terms_id == terms.id,
        )
    )
    if acceptance.scalar_one_or_none():
        return TermsCheckResponse(needs_acceptance=False)

    return TermsCheckResponse(
        needs_acceptance=True,
        terms_id=str(terms.id),
        version=terms.version,
        title=terms.title,
    )
