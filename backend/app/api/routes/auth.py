"""
app/api/routes/auth.py
----------------------
Authentication routes for the platform.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Dict, Any

from app.core.security import create_access_token
from app.core.config import get_settings
from app.api.deps import get_current_user

router = APIRouter(tags=["auth"])

@router.post("/api/auth/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()) -> Dict[str, Any]:
    """
    Authenticate user and return a JWT access token.
    
    Note: Currently uses hardcoded admin credentials for development only.
    In a production environment, this should query a real user database
    and verify hashed passwords.
    """
    settings = get_settings()
    # Dev-only hardcoded credentials check
    if form_data.username != settings.ADMIN_USERNAME or form_data.password != settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(data={"sub": form_data.username})
    return {"access_token": access_token, "token_type": "bearer"}

@router.get("/api/auth/me")
async def get_me(username: str = Depends(get_current_user)) -> Dict[str, str]:
    """Return the current authenticated user's details."""
    return {"username": username, "role": "admin"}

@router.post("/api/auth/refresh")
async def refresh_token(username: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Refresh the current access token for keep-alive."""
    access_token = create_access_token(data={"sub": username})
    return {"access_token": access_token, "token_type": "bearer"}
