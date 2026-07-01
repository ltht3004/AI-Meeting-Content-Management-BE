from pydantic import BaseModel
from typing import Optional

class RecordingResponse(BaseModel):
    id: int
    meeting_id: int
    file_path: str
    status: str
    transcript: Optional[str] = None
    summary: Optional[str] = None

    class Config:
        from_attributes = True
