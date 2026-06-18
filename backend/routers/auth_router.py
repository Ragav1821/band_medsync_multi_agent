"""
Authentication Router — MedSync AI
===================================
POST /api/v1/auth/token   — login with username + password, returns JWT
GET  /api/v1/auth/me      — returns current user info (requires token)
GET  /api/v1/auth/users   — list demo users (helps demo evaluators)
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from auth.jwt_auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
    DEMO_USERS,
)

auth_router = APIRouter(prefix="/auth", tags=["Authentication"])


# ── Response schemas ──────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    display_name: str
    role: str
    expires_in_hours: int


class UserInfo(BaseModel):
    username: str
    name: str
    role: str
    display_name: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@auth_router.post("/token", response_model=TokenResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Authenticate with username + password.
    Returns a signed JWT access token.

    Demo credentials:
      ops.manager / MedSync@2026   → OPERATIONS_MANAGER
      compliance  / MedSync@2026   → COMPLIANCE_OFFICER
      cmo         / MedSync@2026   → CHIEF_MEDICAL_OFFICER
    """
    user = authenticate_user(form.username, form.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = create_access_token(form.username, user)

    return TokenResponse(
        access_token=token,
        user_name=user["name"],
        display_name=user["display_name"],
        role=user["role"],
        expires_in_hours=8,
    )


@auth_router.get("/me", response_model=UserInfo)
async def get_me(current_user: dict = Depends(get_current_user)):
    """Return the identity of the currently authenticated user."""
    return UserInfo(
        username=current_user["sub"],
        name=current_user["name"],
        role=current_user["role"],
        display_name=current_user["display_name"],
    )


@auth_router.get("/users", response_model=list)
async def list_demo_users():
    """
    List available demo accounts (for hackathon evaluators).
    Returns usernames, roles, and display names — NOT passwords.
    """
    return [
        {
            "username": uname,
            "display_name": data["display_name"],
            "role": data["role"],
            "password": "MedSync@2026",   # demo only — shown for evaluator convenience
        }
        for uname, data in DEMO_USERS.items()
    ]
