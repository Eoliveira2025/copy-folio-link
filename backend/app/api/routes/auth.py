"""Authentication endpoints: register, login, refresh, forgot/reset/change password, profile."""

import secrets
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.core.config import get_settings
from app.models.user import User
from app.models.subscription import Subscription, SubscriptionStatus
from app.models.password_reset import PasswordResetToken
from app.schemas.auth import (
    RegisterRequest, LoginRequest, TokenResponse,
    ForgotPasswordRequest, ResetPasswordRequest, ChangePasswordRequest,
    MessageResponse, UserProfileResponse,
)
from app.api.deps import get_current_user

router = APIRouter()
settings = get_settings()
logger = logging.getLogger("app.auth")

RESET_TOKEN_EXPIRE_HOURS = 1


async def _send_reset_email(email: str, token: str):
    """Send password reset email via SMTP or configured provider."""
    import smtplib
    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    smtp_host = getattr(settings, "SMTP_HOST", "") or ""
    smtp_port = getattr(settings, "SMTP_PORT", 587)
    smtp_user = getattr(settings, "SMTP_USER", "") or ""
    smtp_pass = getattr(settings, "SMTP_PASSWORD", "") or ""
    smtp_from = getattr(settings, "SMTP_FROM_EMAIL", "") or smtp_user
    frontend_url = getattr(settings, "FRONTEND_URL", "http://localhost:5173")

    reset_url = f"{frontend_url}/reset-password?token={token}"

    if not smtp_host:
        logger.warning(f"SMTP not configured. Reset URL for {email}: {reset_url}")
        return

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Password Reset — CopyTrade Pro"
        msg["From"] = smtp_from
        msg["To"] = email

        html = f"""
        <html><body>
        <h2>Password Reset</h2>
        <p>You requested a password reset. Click the link below to set a new password:</p>
        <p><a href="{reset_url}" style="background:#22c55e;color:#fff;padding:12px 24px;border-radius:6px;text-decoration:none;font-weight:bold;">Reset Password</a></p>
        <p>This link expires in {RESET_TOKEN_EXPIRE_HOURS} hour(s).</p>
        <p>If you didn't request this, ignore this email.</p>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
            server.starttls()
            if smtp_user and smtp_pass:
                server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, email, msg.as_string())

        logger.info(f"Reset email sent to {email}")
    except Exception as e:
        logger.error(f"Failed to send reset email to {email}: {e}")


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    if body.password != body.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")

    existing = await db.execute(select(User).where(User.email == body.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        full_name=body.full_name,
    )
    db.add(user)
    await db.flush()

    # Create free trial subscription with next_billing_date
    now = datetime.now(timezone.utc)
    trial_end = now + timedelta(days=settings.FREE_TRIAL_DAYS)
    db.add(Subscription(
        user_id=user.id,
        status=SubscriptionStatus.TRIAL,
        trial_start=now,
        trial_end=trial_end,
        next_billing_date=trial_end,
        billing_cycle_days=30,
    ))

    await db.commit()

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    body: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Rate limit login by IP
    from app.middleware.rate_limit import rate_limiter
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"rate_limit:login:{client_ip}"
    if not rate_limiter.check_rate_limit(rate_key, settings.LOGIN_RATE_LIMIT, settings.LOGIN_RATE_WINDOW):
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    return TokenResponse(
        access_token=create_access_token(payload["sub"]),
        refresh_token=create_refresh_token(payload["sub"]),
    )


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    role_result = await db.execute(
        select(UserRoleMapping).where(UserRoleMapping.user_id == user.id)
    )
    role_mapping = role_result.scalar_one_or_none()
    return UserProfileResponse(
        id=str(user.id),
        email=user.email,
        full_name=user.full_name,
        is_active=user.is_active,
        created_at=user.created_at.isoformat(),
        role=role_mapping.role.value if role_mapping else "user",
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_user_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return MessageResponse(message="Password updated successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(body: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Generate a secure reset token and send email. Always returns generic response."""
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    if user:
        # Invalidate any existing unused tokens for this user
        existing = await db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,
            )
        )
        for t in existing.scalars():
            t.used = True

        # Generate secure token
        token = secrets.token_urlsafe(48)
        reset_token = PasswordResetToken(
            user_id=user.id,
            token=token,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=RESET_TOKEN_EXPIRE_HOURS),
        )
        db.add(reset_token)
        await db.commit()

        # Send email (fire-and-forget)
        await _send_reset_email(user.email, token)

    # Generic response for security — don't reveal if email exists
    return MessageResponse(message="If this email exists, a reset link has been sent.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(body: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    """Validate reset token (single-use, not expired) and update password."""
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == body.token)
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    if reset_token.used:
        raise HTTPException(status_code=400, detail="This reset token has already been used")

    if reset_token.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="Reset token has expired")

    # Find user
    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Mark token as used (single-use)
    reset_token.used = True

    # Update password
    user.hashed_password = hash_password(body.new_password)
    await db.commit()

    return MessageResponse(message="Password updated successfully")
