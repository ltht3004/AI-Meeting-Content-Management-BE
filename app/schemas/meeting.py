from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MeetingBase(BaseModel):
    title: str
    description: Optional[str] = None
    scheduled_time: Optional[datetime] = None

class MeetingCreate(MeetingBase):
    pass

class MeetingResponse(MeetingBase):
    id: int
    creator_id: int

    class Config:
        from_attributes = True
