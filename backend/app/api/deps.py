"""
app/api/deps.py
---------------
FastAPI dependencies for injection into routes.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from typing import Optional

from app.core.security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    """
    Dependency to get the current user from the JWT token.
    
    This function extracts the JWT token from the Authorization header,
    decodes it using the security utilities, and returns the username
    from the 'sub' claim. If the token is missing, invalid, or expired,
    it raises an HTTP 401 Unauthorized exception.
    
    This is implemented as a FastAPI dependency (Dependency Injection pattern)
    so it can be easily reused across multiple routes to enforce authentication,
    keeping the route logic clean and decoupled from security concerns.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    return username
