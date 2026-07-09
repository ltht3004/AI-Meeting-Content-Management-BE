import uuid
from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Meeting(Base):
    __tablename__ = "meetings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    meeting_date = Column(DateTime, nullable=False)
    location = Column(String(255), nullable=True)
    duration = Column(Integer, nullable=True)
    participants = Column(Text, nullable=True)

    status = Column(String(20), nullable=False, default="Scheduled")

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now()
    )

    user = relationship("User", back_populates="meetings")
    recordings = relationship("Recording", back_populates="meeting")
    summary = relationship("Summary", back_populates="meeting", uselist=False)