from datetime import timezone
from io import BytesIO
from typing import Optional
import unicodedata
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.user import User
from app.schemas.meeting import MeetingCreate, MeetingUpdate
from app.services.export_service import generate_docx_report, generate_pdf_report

router = APIRouter()


def is_user_inactive(user: User) -> bool:
    return str(user.status).lower() in {"inactive", "unactive"}


def utc_isoformat(value):
    if not value:
        return None

    if value.tzinfo:
        return value.astimezone(timezone.utc).isoformat()

    return value.replace(tzinfo=timezone.utc).isoformat()


def validate_meeting_access(db: Session, meeting: Meeting, current_user_id: Optional[str]) -> None:
    if not current_user_id:
        return

    # A non-admin user can only access meetings they created or joined as a participant.
    try:
        from uuid import UUID as pyUUID
        user_uuid = pyUUID(str(current_user_id))
        current_user = db.query(User).filter(User.id == user_uuid).first()
    except ValueError:
        current_user = None

    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    if is_user_inactive(current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    if current_user.role == "admin":
        return

    user_name = current_user.full_name
    user_email = current_user.email
    user_id_str = str(current_user.id)
    is_creator = meeting.user_id == current_user.id
    is_participant = False

    if meeting.participants:
        is_participant = (
            user_name.lower() in meeting.participants.lower() or
            user_email.lower() in meeting.participants.lower() or
            user_id_str in meeting.participants
        )

    if not is_creator and not is_participant:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: You are not a participant in this meeting"
        )


def format_bytes(size: int) -> str:
    if not size:
        return "0 B"

    units = ["B", "KB", "MB", "GB"]
    value = float(size)
    unit_index = 0

    while value >= 1024 and unit_index < len(units) - 1:
        value /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(value)} {units[unit_index]}"

    return f"{value:.1f} {units[unit_index]}"


def build_export_data(db: Session, meeting: Meeting) -> dict:
    # Collect all meeting-z data in one shape so PDF and DOCX exports stay consistent.
    names_str, details = resolve_participants_names(db, meeting.participants)
    recordings = db.query(Recording).filter(
        Recording.meeting_id == meeting.id
    ).order_by(
        Recording.created_at.desc()
    ).all()

    return {
        "title": meeting.title,
        "description": meeting.description,
        "meeting_date": meeting.meeting_date.strftime("%d/%m/%Y %H:%M") if meeting.meeting_date else None,
        "location": meeting.location,
        "duration": meeting.duration,
        "status": meeting.status,
        "participants": [item["name"] for item in details] if details else [name.strip() for name in names_str.split(",") if name.strip()],
        "summary": meeting.summary.content if meeting.summary else None,
        "recordings": [
            {
                "file_name": recording.file_name,
                "size_label": format_bytes(recording.size)
            }
            for recording in recordings
        ],
        "transcripts": [
            {
                "recording_name": recording.file_name,
                "content": recording.transcript.content if recording.transcript else None
            }
            for recording in recordings
        ]
    }


def resolve_participants_names(db: Session, participants_str: Optional[str]) -> tuple[str, list[dict]]:
    if not participants_str:
        return "", []
        
    # Resolve stored participant UUIDs into display names and status for the frontend.    
    raw_ids = [i.strip() for i in participants_str.split(",") if i.strip()]
    from uuid import UUID as pyUUID
    uuids = []
    invalid_names = []
    for rid in raw_ids:
        try:
            uuids.append(pyUUID(rid))
        except ValueError:
            invalid_names.append(rid)
            
    users = []
    if uuids:
        users = db.query(User).filter(User.id.in_(uuids)).all()
        
    user_map = {str(u.id): u for u in users}
    
    resolved_names = []
    participant_details = []
    
    for rid in raw_ids:
        if rid in user_map:
            user = user_map[rid]
            resolved_names.append(user.full_name)
            participant_details.append({
                "id": str(user.id),
                "name": user.full_name,
                "status": user.status,
                "is_active": not is_user_inactive(user)
            })
        else:
            resolved_names.append("Unknown user")
            participant_details.append({
                "id": None,
                "name": "Unknown user",
                "status": "Unavailable",
                "is_active": False
            })
            
    return ", ".join(resolved_names), participant_details


def resolve_names_to_ids(db: Session, participants_str: Optional[str]) -> Optional[str]:
    if not participants_str:
        return participants_str
        
    # Keep backward compatibility with old name/email payloads while storing UUIDs going forward.
    raw_items = [i.strip() for i in participants_str.split(",") if i.strip()]
    
    from uuid import UUID as pyUUID
    resolved_ids = []
    
    names_to_lookup = []
    for item in raw_items:
        try:
            pyUUID(item)
            resolved_ids.append(item)
        except ValueError:
            names_to_lookup.append(item)
            
    if names_to_lookup:
        users = db.query(User).filter(
            (User.full_name.in_(names_to_lookup)) | (User.email.in_(names_to_lookup))
        ).all()
        
        mapping = {}
        for u in users:
            mapping[u.full_name.lower().strip()] = str(u.id)
            mapping[u.email.lower().strip()] = str(u.id)
            
        for item in raw_items:
            try:
                pyUUID(item)
                continue
            except ValueError:
                pass
                
            lookup_key = item.lower().strip()
            if lookup_key in mapping:
                resolved_ids.append(mapping[lookup_key])
            else:
                resolved_ids.append(item)
                
    return ", ".join(resolved_ids)


def format_meeting_response(db: Session, meeting: Meeting) -> dict:
    names_str, details = resolve_participants_names(db, meeting.participants)
    return {
        "id": str(meeting.id),
        "user_id": str(meeting.user_id),
        "title": meeting.title,
        "description": meeting.description,
        "meeting_date": meeting.meeting_date.isoformat() if meeting.meeting_date else None,
        "location": meeting.location,
        "duration": meeting.duration,
        "participants": names_str,
        "participant_details": details,
        "status": meeting.status,
        "created_at": utc_isoformat(meeting.created_at),
        "updated_at": utc_isoformat(meeting.updated_at),
    }


def format_meeting_detail_response(db: Session, meeting: Meeting) -> dict:
    names_str, details = resolve_participants_names(db, meeting.participants)
    response = format_meeting_response(db, meeting)
    recordings = db.query(Recording).filter(
        Recording.meeting_id == meeting.id
    ).order_by(
        Recording.created_at.desc()
    ).all()
    response["participants"] = names_str
    response["participant_details"] = details
    response["recordings"] = [
        {
            "id": str(recording.id),
            "meeting_id": str(recording.meeting_id),
            "file_name": recording.file_name,
            "file_url": recording.file_url,
            "file_type": recording.file_type,
            "size": recording.size,
            "created_at": utc_isoformat(recording.created_at),
            "updated_at": utc_isoformat(recording.updated_at),
        }
        for recording in recordings
    ]
    return response


@router.get("/")
def get_meetings(
    status: Optional[str] = Query(None, description="Filter meetings by status"),
    search: Optional[str] = Query(None, description="Search meetings by title, description, or location"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(9, ge=1, description="Items per page"),
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID to filter by participants/creator"),
    db: Session = Depends(get_db)
):
    query = db.query(Meeting)
    
    if current_user_id:
        # Admins see all meetings; normal users only see meetings they created or joined.
        try:
            from uuid import UUID as pyUUID
            user_uuid = pyUUID(str(current_user_id))
            current_user = db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            current_user = None

        if current_user:
            if is_user_inactive(current_user):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Account has been disabled"
                )
            if current_user.role != "admin":
                user_name = current_user.full_name
                user_email = current_user.email
                user_id_str = str(current_user.id)
                query = query.filter(
                    (Meeting.user_id == current_user.id) |
                    (Meeting.participants.ilike(f"%{user_name}%")) |
                    (Meeting.participants.ilike(f"%{user_email}%")) |
                    (Meeting.participants.ilike(f"%{user_id_str}%"))
                )

    if status and status.lower() != "all":
        query = query.filter(Meeting.status.ilike(status))
    if search:
        search_filter = f"%{search.strip()}%"
        query = query.filter(
            (Meeting.title.ilike(search_filter)) |
            (Meeting.description.ilike(search_filter)) |
            (Meeting.location.ilike(search_filter))
        )
    
    total_count = query.count()
    # Newest meetings are shown first on both dashboard and meeting list.
    query = query.order_by(Meeting.created_at.desc())
    offset = (page - 1) * page_size
    meetings = query.offset(offset).limit(page_size).all()
    
    resolved_meetings = [format_meeting_response(db, m) for m in meetings]
    
    return {
        "meetings": resolved_meetings,
        "total": total_count
    }


@router.get("/{meeting_id}/export")
def export_meeting_report(
    meeting_id: UUID,
    format: str = Query("pdf", pattern="^(pdf|docx)$"),
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID to validate export permission"),
    db: Session = Depends(get_db)
):
    # Load the meeting first so export permissions and report data use the same source record.
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    validate_meeting_access(db, meeting, current_user_id)

    # Export reuses the same normalized data for both PDF and Word output.
    export_data = build_export_data(db, meeting)

    try:
        # Generate the selected binary report format from the normalized export payload.
        if format == "docx":
            file_buffer = generate_docx_report(export_data)
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            extension = "docx"
        else:
            file_buffer = generate_pdf_report(export_data)
            media_type = "application/pdf"
            extension = "pdf"
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Create a download-safe ASCII filename from the meeting title.
    normalized_title = unicodedata.normalize("NFD", meeting.title)
    ascii_title = "".join(
        ch for ch in normalized_title
        if unicodedata.category(ch) != "Mn"
    )
    safe_title = "".join(
        ch.lower() if ch.isascii() and ch.isalnum() else "-"
        for ch in ascii_title
    ).strip("-")
    while "--" in safe_title:
        safe_title = safe_title.replace("--", "-")

    filename = f"{safe_title or 'meeting'}-report.{extension}"

    return StreamingResponse(
        file_buffer if isinstance(file_buffer, BytesIO) else BytesIO(file_buffer),
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.get("/{meeting_id}")
def get_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID to validate participant permission")
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()

    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    if current_user_id:
        try:
            from uuid import UUID as pyUUID
            user_uuid = pyUUID(str(current_user_id))
            current_user = db.query(User).filter(User.id == user_uuid).first()
        except ValueError:
            current_user = None

        if not current_user:
            raise HTTPException(status_code=404, detail="Mock User not found")

        if is_user_inactive(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been disabled"
            )

        # Admin can view all
        if current_user.role != "admin":
            user_name = current_user.full_name
            user_email = current_user.email
            
            # Check if user is creator or participant
            is_creator = meeting.user_id == current_user.id
            is_participant = False
            if meeting.participants:
                user_id_str = str(current_user.id)
                is_participant = (
                    user_name.lower() in meeting.participants.lower() or
                    user_email.lower() in meeting.participants.lower() or
                    user_id_str in meeting.participants
                )
            
            if not is_creator and not is_participant:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Permission denied: You are not a participant in this meeting"
                )

    # Resolve participant statuses and return details
    return format_meeting_detail_response(db, meeting)


@router.post("/")
def create_meeting(
    meeting: MeetingCreate,
    db: Session = Depends(get_db)
):
    # Validate the creator account before saving the meeting.
    user = db.query(User).filter(User.id == meeting.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if is_user_inactive(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    # Build the meeting record from form data and normalize participants before persisting.
    new_meeting = Meeting(
        user_id=meeting.user_id,
        title=meeting.title,
        description=meeting.description,
        meeting_date=meeting.meeting_date,
        location=meeting.location,
        duration=meeting.duration,
        # Store participant UUIDs, not names, so renamed users still resolve correctly later.
        participants=resolve_names_to_ids(db, meeting.participants),
        status=meeting.status
    )

    db.add(new_meeting)
    db.commit()
    db.refresh(new_meeting)

    return format_meeting_response(db, new_meeting)


@router.put("/{meeting_id}")
def update_meeting(
    meeting_id: UUID,
    meeting_update: MeetingUpdate,
    db: Session = Depends(get_db),
    current_user_id: Optional[str] = Query(None, description="Mock current logged in user ID")
):
    # Load the existing meeting so permission checks and partial updates target one record.
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

        if is_user_inactive(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been disabled"
            )
        if meeting.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Only the creator or an admin can edit this meeting"
            )

    # Only update fields submitted by the edit form.
    update_data = meeting_update.model_dump(exclude_unset=True)
    if "participants" in update_data:
        # Edit form may submit UUIDs or legacy names, so normalize before saving.
        update_data["participants"] = resolve_names_to_ids(db, update_data["participants"])

    for key, value in update_data.items():
        setattr(meeting, key, value)

    db.commit()
    db.refresh(meeting)

    return format_meeting_response(db, meeting)


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

        if is_user_inactive(current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account has been disabled"
            )
        if meeting.user_id != current_user.id and current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permission denied: Only the creator or an admin can delete this meeting"
            )

    db.delete(meeting)
    db.commit()

    return {"message": "Meeting deleted successfully"}
