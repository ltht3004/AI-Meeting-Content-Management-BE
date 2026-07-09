from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas.meeting import MeetingCreate, MeetingUpdate

router = APIRouter()


@router.get("/")
def get_meetings(db: Session = Depends(get_db)):
    return db.query(Meeting).all()


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return meeting


@router.post("/")
def create_meeting(
    meeting: MeetingCreate,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == meeting.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    new_meeting = Meeting(
        user_id=meeting.user_id,
        title=meeting.title,
        description=meeting.description,
        meeting_date=meeting.meeting_date,
        location=meeting.location,
        duration=meeting.duration,
        participants=meeting.participants,
        status=meeting.status
    )

    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    return new_meeting


@router.put("/{meeting_id}")
def update_meeting(
    meeting_id: UUID,
    meeting_update: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Query(None, description="Mock current logged in user ID")
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # If current_user_id is provided, validate permissions
    if current_user_id:
        try:
            from uuid import UUID as pyUUID
            user_uuid = pyUUID(str(current_user_id))
            current_user = db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            current_user = None

        if not current_user:
            raise HTTPException(status_code=404, detail="Mock User not found")
        if meeting.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Only the creator or an admin can edit this meeting"
            )

    update_data = meeting_update.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(meeting, key, value)

    db.commit()
    db.refresh(meeting)

    return meeting


@router.delete("/{meeting_id}")
def delete_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Query(None, description="Mock current logged in user ID")
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    # If current_user_id is provided, validate permissions
    if current_user_id:
        try:
            from uuid import UUID as pyUUID
            user_uuid = pyUUID(str(current_user_id))
            current_user = db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            current_user = None

        if not current_user:
            raise HTTPException(status_code=404, detail="Mock User not found")
        if meeting.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Only the creator or an admin can delete this meeting"
            )

    db.delete(meeting)
    db.commit()

    return {"message": "Meeting deleted successfully"}