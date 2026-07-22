from typing import Optional
from uuid import UUID as PyUUID
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.models.user import User

router = APIRouter()


def is_user_inactive(user: User) -> bool:
    return str(user.status).lower() in {"inactive", "unactive"}


def get_month_bounds():
    # Build month boundaries for comparing current-month meetings with previous month.
    now = datetime.now()
    current_month_start = datetime(now.year, now.month, 1)

    if now.month == 1:
        previous_month_start = datetime(now.year - 1, 12, 1)
    else:
        previous_month_start = datetime(now.year, now.month - 1, 1)

    return previous_month_start, current_month_start


def calculate_growth_percent(current_count: int, previous_count: int):
    # Avoid division by zero when the previous month has no meetings.
    if previous_count == 0:
        if current_count == 0:
            return 0
        return 100

    return round(((current_count - previous_count) / previous_count) * 100)


def get_visible_meetings_query(db: Session, current_user_id: Optional[str]):
    # Start with all meetings, then narrow the query based on the current user's role.
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

    if is_user_inactive(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    if current_user.role == "admin":
        return query

    # Normal users only see meetings they created or joined as participants.
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
    # Reuse one permission-aware meeting query for every dashboard metric.
    visible_meetings_query = get_visible_meetings_query(db, current_user_id)
    meeting_ids_select = visible_meetings_query.with_entities(Meeting.id).statement

    # Count core entities visible to the current user.
    total_meetings = visible_meetings_query.count()
    total_recordings = db.query(Recording).filter(
        Recording.meeting_id.in_(meeting_ids_select)
    ).count()
    total_summaries = db.query(Summary).filter(
        Summary.meeting_id.in_(meeting_ids_select)
    ).count()
    total_transcripts = db.query(Transcript).join(Recording).filter(
        Recording.meeting_id.in_(meeting_ids_select)
    ).count()

    # Calculate real meeting growth from database records, not a hard-coded frontend label.
    previous_month_start, current_month_start = get_month_bounds()
    current_month_meetings = visible_meetings_query.filter(
        Meeting.created_at >= current_month_start
    ).count()
    previous_month_meetings = visible_meetings_query.filter(
        Meeting.created_at >= previous_month_start,
        Meeting.created_at < current_month_start
    ).count()
    meeting_growth_percent = calculate_growth_percent(
        current_month_meetings,
        previous_month_meetings
    )

    # Sum recording file sizes to show actual storage used by visible meetings.
    total_storage_bytes = db.query(
        func.coalesce(func.sum(Recording.size), 0)
    ).filter(
        Recording.meeting_id.in_(meeting_ids_select)
    ).scalar() or 0

    # Estimate time covered by AI summaries using the durations of summarized meetings.
    summarized_duration_minutes = db.query(
        func.coalesce(func.sum(Meeting.duration), 0)
    ).join(
        Summary, Summary.meeting_id == Meeting.id
    ).filter(
        Meeting.id.in_(meeting_ids_select)
    ).scalar() or 0

    # Dashboard shows only the latest 5 meetings to keep the card compact.
    recent_meetings = visible_meetings_query.order_by(
        Meeting.created_at.desc()
    ).limit(5).all()

    # Recent activity merges different event types into one timeline.
    activities = []

    # Meeting creation events.
    recent_meeting_activities = visible_meetings_query.order_by(
        Meeting.created_at.desc()
    ).limit(5).all()
    for meeting in recent_meeting_activities:
        activities.append({
            "title": "Meeting Scheduled",
            "desc": meeting.title,
            "created_at": meeting.created_at.isoformat() if meeting.created_at else None
        })

    # Recording upload events.
    recent_recordings = db.query(Recording, Meeting).join(
        Meeting, Recording.meeting_id == Meeting.id
    ).filter(
        Recording.meeting_id.in_(meeting_ids_select)
    ).order_by(
        Recording.created_at.desc()
    ).limit(5).all()
    for recording, meeting in recent_recordings:
        activities.append({
            "title": "Recording Uploaded",
            "desc": f"{recording.file_name} - {meeting.title}",
            "created_at": recording.created_at.isoformat() if recording.created_at else None
        })

    # Transcript generation events.
    recent_transcripts = db.query(Transcript, Recording, Meeting).join(
        Recording, Transcript.recording_id == Recording.id
    ).join(
        Meeting, Recording.meeting_id == Meeting.id
    ).filter(
        Recording.meeting_id.in_(meeting_ids_select)
    ).order_by(
        Transcript.created_at.desc()
    ).limit(5).all()
    for transcript, recording, meeting in recent_transcripts:
        activities.append({
            "title": "Transcript Generated",
            "desc": meeting.title,
            "created_at": transcript.created_at.isoformat() if transcript.created_at else None
        })

    # AI summary generation events.
    recent_summaries = db.query(Summary, Meeting).join(
        Meeting, Summary.meeting_id == Meeting.id
    ).filter(
        Summary.meeting_id.in_(meeting_ids_select)
    ).order_by(
        Summary.created_at.desc()
    ).limit(5).all()
    for summary, meeting in recent_summaries:
        activities.append({
            "title": "AI Summary Generated",
            "desc": meeting.title,
            "created_at": summary.created_at.isoformat() if summary.created_at else None
        })

    # Sort all activity types together and keep only the newest 5 items.
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
            "total_summaries": total_summaries,
            "meeting_growth_percent": meeting_growth_percent,
            "total_storage_bytes": int(total_storage_bytes),
            "transcript_accuracy_avg": None,
            "summarized_duration_minutes": int(summarized_duration_minutes)
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
