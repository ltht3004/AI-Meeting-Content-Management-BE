from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from uuid import UUID
from datetime import datetime

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=4, description="Tên người dùng phải trên 3 kí tự")
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(None, pattern=r"^\d{10}$", description="Phone number must be exactly 10 digits")

class ChangePassword(BaseModel):
    current_password: str
    new_password: str

class ProfileResponse(BaseModel):
    id: UUID
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    status: str
    avatar_url: Optional[str] = None
    total_quota: int
    used_quota: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ProfileStatsResponse(BaseModel):
    totalMeetings: int
    meetingsGrowth: int
    totalRecordings: int
    recordingsGrowth: int
    totalTranscripts: int
    transcriptsGrowth: int
    totalSummaries: int
    summariesGrowth: int
    usedQuota: int
    totalQuota: int
    resetDate: Optional[str] = None
