
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, UserUpdate, UserResponse, PaginatedUserResponse
from app.api.v1.profile import get_current_user, pending_email_updates
from app.core.security import get_password_hash, verify_password
from app.core.email import send_verification_email
import random
from datetime import datetime, timedelta
from pydantic import BaseModel

router = APIRouter()

def get_current_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user

@router.get("/", response_model=PaginatedUserResponse)
def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    role: Optional[str] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    query = db.query(User)
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            or_(
                User.full_name.ilike(search_term),
                User.email.ilike(search_term),
                User.phone.ilike(search_term)
            )
        )
        
    if role:
        query = query.filter(User.role == role)
        
    if status_filter:
        query = query.filter(User.status == status_filter)
        
    total_count = query.count()
    users = query.order_by(User.created_at.desc()).offset(skip).limit(limit).all()
    
    page = (skip // limit) + 1 if limit > 0 else 1
    
    return {
        "items": users,
        "total_count": total_count,
        "page": page,
        "limit": limit
    }

@router.get("/{user_id}", response_model=UserResponse)
def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    user_in: UserCreate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.email == user_in.email).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system."
        )

    if user_in.phone:
        user_phone = db.query(User).filter(User.phone == user_in.phone).first()
        if user_phone:
            raise HTTPException(
                status_code=400,
                detail="The user with this phone number already exists in the system."
            )
        
    user_data = user_in.model_dump(exclude={"password"})
    hashed_password = get_password_hash(user_in.password)
    
    db_user = User(
        **user_data,
        password=hashed_password
    )
    
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.put("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: str,
    user_in: UserUpdate,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user_in.email and user_in.email != user.email:
        raise HTTPException(
            status_code=400,
            detail="Admin cannot change user email. Email editing is locked for security reasons."
        )

    if user_in.phone and user_in.phone != user.phone:
        existing_phone = db.query(User).filter(User.phone == user_in.phone).first()
        if existing_phone:
            raise HTTPException(
                status_code=400,
                detail="Phone number is already in use by another user."
            )
            
    update_data = user_in.model_dump(exclude_unset=True)
    # Remove email from update_data just to be absolutely sure
    update_data.pop("email", None)
    
    for field, value in update_data.items():
        if value is not None:
            setattr(user, field, value)
        
    db.commit()
    db.refresh(user)
    
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_admin: User = Depends(get_current_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if str(user.id) == str(current_admin.id):
        raise HTTPException(status_code=400, detail="Admins cannot delete their own account via this endpoint.")
        
    # We perform a soft delete by changing status, or hard delete. 
    # The plan says "soft delete or completely remove". 
    # To be safer for data integrity (due to foreign keys), let's hard delete if we want true "delete", 
    # but soft deleting is better. I will hard delete for simplicity unless the user specifies.
    # Actually, the user asked to remove is_active because "có cột status quản lý rồi".
    # So I should do a Soft Delete by setting status="Inactive".
    user.status = "Inactive"
    db.commit()
    return None

@router.get("/{user_id}/stats")
def get_user_stats(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.meeting import Meeting
    from app.models.recording import Recording
    from app.models.summary import Summary

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    total_meetings = db.query(Meeting).filter(Meeting.user_id == user_id).count()
    
    total_recordings = db.query(Recording).join(Meeting).filter(Meeting.user_id == user_id).count()
    
    total_summaries = db.query(Summary).join(Meeting).filter(Meeting.user_id == user_id).count()

    return {
        "totalMeetings": total_meetings,
        "totalRecordings": total_recordings,
        "totalSummaries": total_summaries,
        "meetingsGrowth": 0,
        "recordingsGrowth": 0

    }
