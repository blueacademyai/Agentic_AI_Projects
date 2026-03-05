from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr, validator
from typing import Optional
import logging
from datetime import datetime

from ..database import get_db
from ..models import User
from ..auth import (
    authenticate_user, create_user_tokens, get_password_hash,
    validate_password_strength, get_current_user, verify_verification_token,
    generate_verification_token, get_user_by_email
)
from ..utils.email_service import send_verification_email, send_welcome_email

logger = logging.getLogger(__name__)
router = APIRouter()

# Pydantic models for request/response
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: Optional[str] = "user"
    
    @validator('role')
    def validate_role(cls, v):
        if v not in ['user', 'admin']:
            raise ValueError('Role must be either user or admin')
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
    user: dict

class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    is_verified: bool
    created_at: datetime

class PasswordChange(BaseModel):
    current_password: str
    new_password: str
    
    @validator('new_password')
    def validate_password(cls, v):
        validation = validate_password_strength(v)
        if not validation['is_valid']:
            raise ValueError(f"Password validation failed: {', '.join(validation['issues'])}")
        return v

class EmailVerification(BaseModel):
    token: str

@router.post("/signup", response_model=dict, status_code=status.HTTP_201_CREATED)
async def signup(
    user_data: UserSignup,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Register a new user"""
    try:
        # Check if user already exists
        existing_user = get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Validate password strength
        password_validation = validate_password_strength(user_data.password)
        if not password_validation['is_valid']:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Password does not meet requirements",
                    "issues": password_validation['issues']
                }
            )
        
        # Create new user
        hashed_password = get_password_hash(user_data.password)
        db_user = User(
            email=user_data.email,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            phone=user_data.phone,
            role=user_data.role,
            is_active=True,
            is_verified=False
        )
        
        db.add(db_user)
        db.commit()
        db.refresh(db_user)
        
        # Generate verification token and send email
        verification_token = generate_verification_token(db_user.id)
        background_tasks.add_task(
            send_verification_email,
            db_user.email,
            db_user.full_name or db_user.email,
            verification_token
        )
        
        logger.info(f"New user registered: {user_data.email}")
        
        return {
            "message": "User registered successfully",
            "user_id": db_user.id,
            "verification_sent": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup error: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )

@router.post("/login", response_model=TokenResponse)
async def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    """Authenticate user and return tokens"""
    try:
        # Authenticate user
        user = authenticate_user(db, user_data.email, user_data.password)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        # Create tokens
        tokens = create_user_tokens(user)
        
        # Update last login time
        user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"User logged in: {user.email}")
        
        return tokens
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed"
        )

@router.post("/verify-email")
async def verify_email(
    verification_data: EmailVerification,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Verify user email address"""
    try:
        # Verify token
        user_id = verify_verification_token(verification_data.token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification token"
            )
        
        # Get user and verify
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        if user.is_verified:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already verified"
            )
        
        # Mark user as verified
        user.is_verified = True
        user.updated_at = datetime.utcnow()
        db.commit()
        
        # Send welcome email
        background_tasks.add_task(
            send_welcome_email,
            user.email,
            user.full_name or user.email
        )
        
        logger.info(f"Email verified for user: {user.email}")
        
        return {"message": "Email verified successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Email verification error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Email verification failed"
        )

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change user password"""
    try:
        # Verify current password
        from auth import verify_password
        if not verify_password(password_data.current_password, current_user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is incorrect"
            )
        
        # Update password
        current_user.hashed_password = get_password_hash(password_data.new_password)
        current_user.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(f"Password changed for user: {current_user.email}")
        
        return {"message": "Password changed successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Password change error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Password change failed"
        )

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role=current_user.role,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        created_at=current_user.created_at
    )

@router.post("/logout")
async def logout(current_user: User = Depends(get_current_user)):
    """Logout user (client should discard tokens)"""
    logger.info(f"User logged out: {current_user.email}")
    return {"message": "Logged out successfully"}

@router.post("/refresh-token")
async def refresh_token(
    refresh_token: str,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        from jose import jwt, JWTError
        from auth import SECRET_KEY, ALGORITHM, create_access_token
        
        # Verify refresh token
        try:
            payload = jwt.decode(refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type"
                )
            
            user_id = payload.get("user_id")
            email = payload.get("sub")
            role = payload.get("role")
            
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Verify user still exists and is active
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        token_data = {
            "sub": email,
            "user_id": user_id,
            "role": role
        }
        new_access_token = create_access_token(token_data)
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed"
        )