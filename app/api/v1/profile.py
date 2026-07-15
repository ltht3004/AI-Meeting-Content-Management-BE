import os
import uuid
import shutil
import cloudinary
import cloudinary.uploader
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
from pydantic import BaseModel
import random
from datetime import datetime, timedelta
from app.core.email import send_verification_email

router = APIRouter()
security = HTTPBearer()

cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)

pending_email_updates = {}

class VerifyEmailChange(BaseModel):
    code: str

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
    requires_email_verification = False
    
    if profile_data.full_name is not None:
        current_user.full_name = profile_data.full_name
        
    if profile_data.email is not None and profile_data.email != current_user.email:
        existing_user = db.query(User).filter(User.email == profile_data.email, User.id != current_user.id).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is already in use"
            )
            
        code = f"{random.randint(100000, 999999)}"
        pending_email_updates[current_user.id] = {
            "new_email": profile_data.email,
            "code": get_password_hash(code),
            "expires_at": datetime.utcnow() + timedelta(minutes=15)
        }
        send_verification_email(profile_data.email, code)
        requires_email_verification = True
        
    if hasattr(profile_data, 'phone') and profile_data.phone is not None:
        existing_phone = db.query(User).filter(User.phone == profile_data.phone, User.id != current_user.id).first()
        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is already in use"
            )
        current_user.phone = profile_data.phone
        
    db.commit()
    db.refresh(current_user)
    
    response_dict = {
        "id": current_user.id,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "phone": current_user.phone,
        "role": current_user.role,
        "status": current_user.status,
        "avatar_url": current_user.avatar_url,
        "total_quota": current_user.total_quota,
        "used_quota": current_user.used_quota,
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "requires_email_verification": requires_email_verification
    }
    return response_dict

@router.post("/me/verify-email", response_model=ProfileResponse)
def verify_email_update(
    req: VerifyEmailChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pending_update = pending_email_updates.get(current_user.id)
    if not pending_update:
        raise HTTPException(status_code=400, detail="No pending email update found or session expired")
        
    if not verify_password(req.code, pending_update["code"]):
        raise HTTPException(status_code=400, detail="Invalid verification code")
        
    if pending_update["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Verification code has expired")
        
    current_user.email = pending_update["new_email"]
    db.commit()
    db.refresh(current_user)
    
    del pending_email_updates[current_user.id]
    
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
    
    # Remove old avatar if exists
    if current_user.avatar_url:
        if "res.cloudinary.com" in current_user.avatar_url:
            try:
                public_id = current_user.avatar_url.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(f"meeting_avatars/{public_id}")
            except Exception as e:
                pass
        else:
            old_filename = current_user.avatar_url.split('/')[-1]
            old_filepath = os.path.join("uploads", "avatars", old_filename)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except:
                    pass
            
    # Save file locally first to avoid stream hanging issues
    import uuid
    import os
    import shutil
    ext = file.filename.split('.')[-1]
    temp_filename = f"temp_{uuid.uuid4()}.{ext}"
    temp_filepath = os.path.join("uploads", temp_filename)
    os.makedirs("uploads", exist_ok=True)
    
    with open(temp_filepath, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    # Upload to Cloudinary
    try:
        upload_result = cloudinary.uploader.upload(
            temp_filepath,
            folder="meeting_avatars",
            transformation=[
                {'width': 300, 'height': 300, 'crop': "fill", 'gravity': "face"}
            ]
        )
        
        # Clean up temp file
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
            
        current_user.avatar_url = upload_result.get("secure_url")
        db.commit()
        db.refresh(current_user)
        return {"avatar_url": current_user.avatar_url}
    except Exception as e:
        # Clean up temp file on error
        if os.path.exists(temp_filepath):
            os.remove(temp_filepath)
        raise HTTPException(status_code=500, detail=f"Error uploading image to Cloudinary: {str(e)}")

@router.delete("/me/avatar")
def remove_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.avatar_url:
        if "res.cloudinary.com" in current_user.avatar_url:
            try:
                public_id = current_user.avatar_url.split('/')[-1].split('.')[0]
                cloudinary.uploader.destroy(f"meeting_avatars/{public_id}")
            except Exception as e:
                pass
        else:
            old_filename = current_user.avatar_url.split('/')[-1]
            old_filepath = os.path.join("uploads", "avatars", old_filename)
            if os.path.exists(old_filepath):
                try:
                    os.remove(old_filepath)
                except:
                    pass
            
        current_user.avatar_url = None
        db.commit()
        db.refresh(current_user)
        
    return {"message": "Avatar removed successfully"}
