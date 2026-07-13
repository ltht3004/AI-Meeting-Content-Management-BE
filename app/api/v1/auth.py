import random
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.core.security import get_password_hash, verify_password, create_access_token
from app.core.email import send_reset_code_email, send_verification_email

router = APIRouter()

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

class ForgotPasswordRequest(BaseModel):
    email: EmailStr

class ResetPasswordRequest(BaseModel):
    email: EmailStr
    reset_code: str
    new_password: str

class VerifyEmailRequest(BaseModel):
    email: EmailStr
    code: str

class RegisterResponse(BaseModel):
    message: str
    email: str

@router.post("/register", response_model=RegisterResponse)
def register(user: UserCreate, db: Session = Depends(get_db)):
    existed_user = db.query(User).filter(User.email == user.email).first()

    if existed_user:
        raise HTTPException(status_code=400, detail="Email already exists")

    existed_phone = db.query(User).filter(User.phone == user.phone).first()
    if existed_phone:
        raise HTTPException(status_code=400, detail="Phone number already exists")

    code = f"{random.randint(100000, 999999)}"
    
    new_user = User(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        password=get_password_hash(user.password),
        role=user.role or "user",
        status="Pending",
        reset_code=get_password_hash(code),
        reset_code_expires_at=datetime.utcnow() + timedelta(minutes=15)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    send_verification_email(new_user.email, code)
    
    return {
        "message": "Verification email sent. Please check your inbox.",
        "email": new_user.email
    }

@router.post("/verify-email", response_model=TokenResponse)
def verify_email(req: VerifyEmailRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    
    if not user or not user.reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
        
    if not verify_password(req.code, user.reset_code):
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")
    
    if user.reset_code_expires_at and user.reset_code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code has expired")
        
    user.status = "Active"
    user.reset_code = None
    user.reset_code_expires_at = None
    db.commit()
    
    access_token = create_access_token(subject=user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/login", response_model=TokenResponse)
def login(user: UserLogin, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.email == user.email).first()

    if not db_user:
        raise HTTPException(status_code=404, detail="Email does not exist")

    if not verify_password(user.password, db_user.password):
        raise HTTPException(status_code=400, detail="Incorrect password")

    if db_user.status == "Unactive":
        raise HTTPException(status_code=403, detail="Account has been disabled")

    access_token = create_access_token(subject=db_user.id)
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user
    }

@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        # Prevent email enumeration by returning generic success
        return {"message": "If the email exists, a reset code has been sent."}
    
    code = f"{random.randint(100000, 999999)}"
    user.reset_code = get_password_hash(code)
    user.reset_code_expires_at = datetime.utcnow() + timedelta(minutes=15)
    db.commit()
    
    send_reset_code_email(user.email, code)
    return {"message": "If the email exists, a reset code has been sent."}

@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user or not user.reset_code:
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
        
    if not verify_password(req.reset_code, user.reset_code):
        raise HTTPException(status_code=400, detail="Invalid or expired reset code")
    
    if user.reset_code_expires_at and user.reset_code_expires_at < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Reset code has expired")
    
    # We should validate password strength here or rely on the frontend
    # Since we added Pydantic validation on UserCreate earlier, let's manually check here or trust frontend
    user.password = get_password_hash(req.new_password)
    user.reset_code = None
    user.reset_code_expires_at = None
    db.commit()
    return {"message": "Password has been reset successfully"}
