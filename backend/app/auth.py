"""
Authentication utilities for verifying JWT tokens from Supabase.
"""
import os
import jwt
from typing import Optional, Dict, Any
from fastapi import HTTPException, Header
from dotenv import load_dotenv

load_dotenv()

# Supabase JWT configuration
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

# For development, we can also use the service role key as secret
if not SUPABASE_JWT_SECRET:
    SUPABASE_JWT_SECRET = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def verify_token(authorization: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Verify JWT token from Authorization header.
    Returns the decoded token payload with user information.
    """
    if not authorization:
        return None

    try:
        # Extract token from "Bearer <token>" format
        if not authorization.startswith("Bearer "):
            return None

        token = authorization.replace("Bearer ", "")

        # Decode and verify JWT token
        # Supabase uses HS256 algorithm
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"verify_signature": True}
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        print(f"Token verification error: {e}")
        return None


def get_user_id(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Extract user ID from JWT token.
    """
    payload = verify_token(authorization)
    if not payload:
        return None

    return payload.get("sub")  # "sub" contains the user ID


def require_auth(authorization: Optional[str] = Header(None)) -> str:
    """
    Require authentication. Raises 401 if not authenticated.
    Returns the user ID.
    """
    user_id = get_user_id(authorization)

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Please log in."
        )

    return user_id


def optional_auth(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Optional authentication. Returns user ID if authenticated, None otherwise.
    Does not raise errors.
    """
    try:
        return get_user_id(authorization)
    except:
        return None
