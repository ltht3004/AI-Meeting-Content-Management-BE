from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

class RecordingResponse(BaseModel):
    id: UUID
    meeting_id: UUID
    file_name: str
    file_url: str
    file_type: str
    size: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    class Config:
        from_attributes = True
