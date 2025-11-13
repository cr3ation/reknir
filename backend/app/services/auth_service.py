"""
Authentication service for password hashing and JWT token management
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.schemas.user import TokenData


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a plain password against a hashed password

    Args:
        plain_password: Plain text password from user input
        hashed_password: Hashed password from database

    Returns:
        True if password matches, False otherwise
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """
    Hash a plain password using bcrypt

    Args:
        password: Plain text password

    Returns:
        Hashed password string
    """
    return pwd_context.hash(password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary of data to encode in the token (user_id, email, etc.)
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.access_token_expire_minutes)

    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=settings.algorithm)

    return encoded_jwt


def decode_access_token(token: str) -> Optional[TokenData]:
    """
    Decode and validate a JWT access token

    Args:
        token: JWT token string

    Returns:
        TokenData if valid, None if invalid or expired
    """
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        print(f"DEBUG: JWT payload decoded: {payload}")
        sub: str = payload.get("sub")
        email: str = payload.get("email")
        is_admin: bool = payload.get("is_admin", False)

        if sub is None or email is None:
            print(f"DEBUG: sub or email is None, returning None")
            return None

        # Convert sub (string) to user_id (int)
        try:
            user_id = int(sub)
        except (ValueError, TypeError):
            print(f"DEBUG: Failed to convert sub to int: {sub}")
            return None

        print(f"DEBUG: Extracted from payload - user_id={user_id}, email={email}, is_admin={is_admin}")

        return TokenData(user_id=user_id, email=email, is_admin=is_admin)
    except JWTError as e:
        print(f"DEBUG: JWTError occurred: {e}")
        return None


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """
    Authenticate a user by email and password

    Args:
        db: Database session
        email: User email
        password: Plain text password

    Returns:
        User object if authentication successful, None otherwise
    """
    user = db.query(User).filter(User.email == email).first()

    if not user:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def create_user(db: Session, email: str, password: str, full_name: str, is_admin: bool = False) -> User:
    """
    Create a new user with hashed password

    Args:
        db: Database session
        email: User email
        password: Plain text password (will be hashed)
        full_name: User's full name
        is_admin: Whether user is admin (default False)

    Returns:
        Created User object
    """
    hashed_password = get_password_hash(password)

    user = User(
        email=email,
        hashed_password=hashed_password,
        full_name=full_name,
        is_admin=is_admin,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user
