"""
JWT Authentication — MedSync AI (Phase 16 Security Hardening)
=============================================================

Provides:
  - Demo user registry with hashed passwords (stdlib hashlib, no extra deps)
  - JWT token creation and verification via PyJWT
  - FastAPI dependency: require_approver (OPERATIONS_MANAGER | COMPLIANCE_OFFICER | CMO)
  - FastAPI dependency: get_current_user (any authenticated user)

Demo credentials (for hackathon — swap for real IdP in production):
  Username          Password          Role
  ──────────────────────────────────────────────────────────────
  ops.manager       MedSync@2026      OPERATIONS_MANAGER
  compliance        MedSync@2026      COMPLIANCE_OFFICER
  cmo               MedSync@2026      CHIEF_MEDICAL_OFFICER
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from config.settings import settings

logger = logging.getLogger(__name__)

# ── OAuth2 scheme — points to our login endpoint ─────────────────────────────
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

# ── Roles allowed to approve action plans ─────────────────────────────────────
APPROVER_ROLES = {"OPERATIONS_MANAGER", "COMPLIANCE_OFFICER", "CHIEF_MEDICAL_OFFICER"}


# ── Demo user registry ─────────────────────────────────────────────────────────
# Passwords are stored as PBKDF2-SHA256 hashes (stdlib, no extra packages).
# To regenerate a hash:  _hash_password("YourPassword")

def _hash_password(plain: str) -> str:
    """One-way PBKDF2-SHA256 hash with a fixed demo salt."""
    # Fixed salt for demo — in production use per-user random salt stored in DB
    salt = b"medsync_demo_salt_2026"
    dk = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt, 260_000)
    return dk.hex()


# Pre-computed hashes for "MedSync@2026"
_DEMO_PASSWORD_HASH = _hash_password("MedSync@2026")

DEMO_USERS: dict[str, dict] = {
    "ops.manager": {
        "password_hash": _DEMO_PASSWORD_HASH,
        "name": "Alex Chen",
        "role": "OPERATIONS_MANAGER",
        "display_name": "Operations Manager — Alex Chen",
    },
    "compliance": {
        "password_hash": _DEMO_PASSWORD_HASH,
        "name": "Dr. Sarah Kim",
        "role": "COMPLIANCE_OFFICER",
        "display_name": "Compliance Officer — Dr. Sarah Kim",
    },
    "cmo": {
        "password_hash": _DEMO_PASSWORD_HASH,
        "name": "Dr. James Rivera",
        "role": "CHIEF_MEDICAL_OFFICER",
        "display_name": "Chief Medical Officer — Dr. James Rivera",
    },
}


# ── Password verification ──────────────────────────────────────────────────────

def verify_password(plain: str, stored_hash: str) -> bool:
    """Constant-time password comparison via hmac."""
    return hmac.compare_digest(_hash_password(plain), stored_hash)


def authenticate_user(username: str, password: str) -> Optional[dict]:
    """Return user dict if credentials are valid, else None."""
    user = DEMO_USERS.get(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"username": username, **user}


# ── Token creation ─────────────────────────────────────────────────────────────

def create_access_token(username: str, user: dict) -> str:
    """Encode a signed JWT containing the user's identity and role."""
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "sub": username,
        "name": user["name"],
        "role": user["role"],
        "display_name": user["display_name"],
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


# ── Token verification ─────────────────────────────────────────────────────────

def decode_token(token: str) -> dict:
    """
    Decode and validate a JWT.
    Raises HTTPException 401 on invalid/expired token.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        logger.warning("[auth] Invalid token: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependencies ───────────────────────────────────────────────────────

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    """FastAPI dependency — any authenticated user."""
    return decode_token(token)


async def require_approver(token: str = Depends(oauth2_scheme)) -> dict:
    """
    FastAPI dependency — caller must have an approver role.
    Used on: PATCH /action-plans/{plan_id}/approve
    """
    user = decode_token(token)
    if user.get("role") not in APPROVER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Role '{user.get('role')}' is not authorised to approve action plans. "
                   f"Required: {sorted(APPROVER_ROLES)}",
        )
    return user
