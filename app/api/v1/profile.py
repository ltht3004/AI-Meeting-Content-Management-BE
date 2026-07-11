import os
import uuid
import shutil
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt, JWTError
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.config import settings
from app.models.user import User
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.transcript import Transcript
from app.models.summary import Summary
from app.schemas.profile import ProfileResponse, ProfileUpdate, ChangePassword, ProfileStatsResponse
from app.core.security import verify_password, get_password_hash

router = APIRouter()
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or expired"
        )
    
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    return user

@router.get("/me", response_model=ProfileResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me/stats", response_model=ProfileStatsResponse)
def get_profile_stats(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    total_meetings = db.query(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_recordings = db.query(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_transcripts = db.query(Transcript).join(Recording).join(Meeting).filter(Meeting.user_id == current_user.id).count()
    total_summaries = db.query(Summary).join(Meeting).filter(Meeting.user_id == current_user.id).count()

    reset_date_str = current_user.reset_date.strftime("%b %d, %Y") if current_user.reset_date else "N/A"

    return {
        "totalMeetings": total_meetings,
        "meetingsGrowth": 0,
        "totalRecordings": total_recordings,
        "recordingsGrowth": 0,
        "totalTranscripts": total_transcripts,
        "transcriptsGrowth": 0,
        "totalSummaries": total_summaries,
        "summariesGrowth": 0,
        "usedQuota": current_user.used_quota or 0,
        "totalQuota": current_user.total_quota or 600,
        "resetDate": reset_date_str
    }

@router.put("/me", response_model=ProfileResponse)
def update_profile(
    profile_data: ProfileUpdate, 
    current_user: User = Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
    if profile_data.email is not None:
        existing_user = db.query(User).filter(User.email == profile_data.email, User.id != current_user.id).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use"
            )
        current_user.email = profile_data.email
    if hasattr(profile_data, 'phone') and profile_data.phone is not None:
        current_user.phone = profile_data.phone
        
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/password")
def change_password(
    password_data: ChangePassword,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not verify_password(password_data.current_password, current_user.password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password"
        )
    
    current_user.password = get_password_hash(password_data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@router.post("/me/avatar")
def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    ext = file.filename.split('.')[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    filepath = os.path.join("uploads", "avatars", filename)
    
    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split('/')[-1]
        old_filepath = os.path.join("uploads", "avatars", old_filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
            
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    current_user.avatar_url = f"/uploads/avatars/{filename}"
    db.commit()
    db.refresh(current_user)
    
    return {"avatar_url": current_user.avatar_url}

@router.delete("/me/avatar")
def remove_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.avatar_url:
        old_filename = current_user.avatar_url.split('/')[-1]
        old_filepath = os.path.join("uploads", "avatars", old_filename)
        if os.path.exists(old_filepath):
            os.remove(old_filepath)
            
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
        
    return {"message": "Avatar removed successfully"}
