"""FastAPI application entrypoint with rate limiting middleware."""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger("app.main")


def _get_cors_origins() -> list[str]:
    """Resolve CORS origins from environment. Fail in production if not set."""
    if settings.ALLOWED_ORIGINS:
        return [o.strip() for o in settings.ALLOWED_ORIGINS.split(",") if o.strip()]

    if settings.ENVIRONMENT == "production":
        logger.critical("ALLOWED_ORIGINS is not set in production! Refusing to start with wildcard CORS.")
        sys.exit(1)

    # Development default
    return [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:5173",
    ]


async def _ensure_default_admin():
    """Create default admin user if none exists. Runs once at startup."""
    from app.core.database import AsyncSessionLocal
    from app.models.user import User, UserRole, UserRoleMapping
    from app.core.security import hash_password
    from sqlalchemy import select

    try:
        async with AsyncSessionLocal() as db:
            # Check if any admin exists
            result = await db.execute(
                select(UserRoleMapping).where(UserRoleMapping.role == UserRole.ADMIN)
            )
            if result.scalar_one_or_none():
                return  # Admin already exists

            # Use configured admin credentials
            email = "admin@copytrade.com"
            password = "admin123.0@"

            existing = await db.execute(select(User).where(User.email == email))
            user = existing.scalar_one_or_none()

            if not user:
                user = User(
                    email=email,
                    hashed_password=hash_password(password),
                    full_name="Admin",
                    is_active=True,
                )
                db.add(user)
                await db.flush()

            db.add(UserRoleMapping(user_id=user.id, role=UserRole.ADMIN))
            await db.commit()
            logger.info("Default admin user created (admin@copytrade.com)")
    except Exception as e:
        logger.warning(f"Could not create default admin (tables may not exist yet): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_default_admin()
    yield


from app.api import api_router

app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
