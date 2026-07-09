from uuid import UUID
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    meeting_date: datetime
    location: Optional[str] = None
    duration: Optional[int] = None
    participants: Optional[str] = None
    status: Optional[str] = "Scheduled"


class MeetingCreate(MeetingBase):
    user_id: UUID


class MeetingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    meeting_date: Optional[datetime] = None
    location: Optional[str] = None
    duration: Optional[int] = None
    participants: Optional[str] = None
    status: Optional[str] = None


class MeetingResponse(MeetingBase):
    id: UUID
    user_id: UUID

    class Config:
        from_attributes = True