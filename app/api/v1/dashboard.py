from typing import Optional
from uuid import UUID as PyUUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.models.user import User

router = APIRouter()


def get_visible_meetings_query(db: Session, current_user_id: Optional[str]):
    query = db.query(Meeting)

    if not current_user_id:
        return query

    try:
        user_uuid = PyUUID(str(current_user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid current user ID")

    current_user = db.query(User).filter(User.id == user_uuid).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    if current_user.status == "Unactive" or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    if current_user.role == "admin":
        return query

    user_name = current_user.full_name
    user_email = current_user.email
    user_id_str = str(current_user.id)

    return query.filter(
        (Meeting.user_id == current_user.id) |
        (Meeting.participants.ilike(f"%{user_name}%")) |
        (Meeting.participants.ilike(f"%{user_email}%")) |
        (Meeting.participants.ilike(f"%{user_id_str}%"))
    )


@router.get("/summary")
def get_dashboard_summary(
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID"),
    db: Session = Depends(get_db)
):
    visible_meetings_query = get_visible_meetings_query(db, current_user_id)
    meeting_ids_subquery = visible_meetings_query.with_entities(Meeting.id).subquery()

    total_meetings = visible_meetings_query.count()
    total_recordings = db.query(Recording).filter(
        Recording.meeting_id.in_(meeting_ids_subquery)
    ).count()
    total_summaries = db.query(Summary).filter(
        Summary.meeting_id.in_(meeting_ids_subquery)
    ).count()
    total_transcripts = db.query(Transcript).join(Recording).filter(
        Recording.meeting_id.in_(meeting_ids_subquery)
    ).count()

    recent_meetings = visible_meetings_query.order_by(
        Meeting.created_at.desc()
    ).limit(5).all()

    activities = []

    recent_meeting_activities = visible_meetings_query.order_by(
        Meeting.created_at.desc()
    ).limit(5).all()
    for meeting in recent_meeting_activities:
        activities.append({
            "title": "Meeting Scheduled",
            "desc": meeting.title,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None
        })

    recent_recordings = db.query(Recording, Meeting).join(
        Meeting, Recording.meeting_id == Meeting.id
    ).filter(
        Recording.meeting_id.in_(meeting_ids_subquery)
    ).order_by(
        Recording.created_at.desc()
    ).limit(5).all()
    for recording, meeting in recent_recordings:
        activities.append({
            "title": "Recording Uploaded",
            "desc": f"{recording.file_name} - {meeting.title}",
            "created_at": recording.created_at.isoformat() if recording.created_at else None
        })

    recent_transcripts = db.query(Transcript, Recording, Meeting).join(
        Recording, Transcript.recording_id == Recording.id
    ).join(
        Meeting, Recording.meeting_id == Meeting.id
    ).filter(
        Recording.meeting_id.in_(meeting_ids_subquery)
    ).order_by(
        Transcript.created_at.desc()
    ).limit(5).all()
    for transcript, recording, meeting in recent_transcripts:
        activities.append({
            "title": "Transcript Generated",
            "desc": meeting.title,
            "created_at": transcript.created_at.isoformat() if transcript.created_at else None
        })

    recent_summaries = db.query(Summary, Meeting).join(
        Meeting, Summary.meeting_id == Meeting.id
    ).filter(
        Summary.meeting_id.in_(meeting_ids_subquery)
    ).order_by(
        Summary.created_at.desc()
    ).limit(5).all()
    for summary, meeting in recent_summaries:
        activities.append({
            "title": "AI Summary Generated",
            "desc": meeting.title,
            "created_at": summary.created_at.isoformat() if summary.created_at else None
        })

    recent_activities = sorted(
        activities,
        key=lambda activity: activity["created_at"] or "",
        reverse=True
    )[:5]

    return {
        "stats": {
            "total_meetings": total_meetings,
            "total_recordings": total_recordings,
            "total_transcripts": total_transcripts,
            "total_summaries": total_summaries
        },
        "recent_meetings": [
            {
                "id": str(meeting.id),
                "title": meeting.title,
                "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
                "status": meeting.status
            }
            for meeting in recent_meetings
        ],
        "recent_activities": recent_activities
    }
