from sqlalchemy import Column, Integer, String, ForeignKey, Text
from app.core.database import Base

class Recording(Base):
    __tablename__ = "recordings"
    
    id = Column(Integer, primary_key=True, index=True)
    meeting_id = Column(Integer, ForeignKey("meetings.id"), unique=True)
    file_path = Column(String, nullable=False)
    status = Column(String, default="processing")
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
