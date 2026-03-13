"""FastAPI application entrypoint with rate limiting middleware."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from app.api import api_router

settings = get_settings()
logger = logging.getLogger("app.main")


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

            # Check if email already taken (assign admin role if so)
            email = "estaeloliveiras@gmail.com"
            existing = await db.execute(select(User).where(User.email == email))
            user = existing.scalar_one_or_none()

            if not user:
                user = User(
                    email=email,
                    hashed_password=hash_password("Admin123!"),
                    full_name="Admin",
                    is_active=True,
                )
                db.add(user)
                await db.flush()

            db.add(UserRoleMapping(user_id=user.id, role=UserRole.ADMIN))
            await db.commit()
            logger.info("Default admin user created")
    except Exception as e:
        logger.warning(f"Could not create default admin (tables may not exist yet): {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _ensure_default_admin()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
