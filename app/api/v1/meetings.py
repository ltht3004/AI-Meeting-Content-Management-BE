from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.user import User
from app.schemas.meeting import MeetingCreate, MeetingUpdate

router = APIRouter()


def is_user_inactive(user: User) -> bool:
    return str(user.status).lower() == "unactive"


def resolve_participants_names(db: Session, participants_str: Optional[str]) -> tuple[str, list[dict]]:
    if not participants_str:
        return "", []
        
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
            resolved_names.append(rid)
            participant_details.append({
                "id": rid,
                "name": rid,
                "status": "Active",
                "is_active": True
            })
            
    return ", ".join(resolved_names), participant_details


def resolve_names_to_ids(db: Session, participants_str: Optional[str]) -> Optional[str]:
    if not participants_str:
        return participants_str
        
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
        "created_at": meeting.created_at.isoformat() if meeting.created_at else None,
        "updated_at": meeting.updated_at.isoformat() if meeting.updated_at else None,
    }


def format_meeting_detail_response(db: Session, meeting: Meeting) -> dict:
    names_str, details = resolve_participants_names(db, meeting.participants)
    response = format_meeting_response(db, meeting)
    response["participants"] = names_str
    response["participant_details"] = details
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
    query = query.order_by(Meeting.created_at.desc())
    offset = (page - 1) * page_size
    meetings = query.offset(offset).limit(page_size).all()
    
    resolved_meetings = [format_meeting_response(db, m) for m in meetings]
    
    return {
        "meetings": resolved_meetings,
        "total": total_count
    }


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
    user = db.query(User).filter(User.id == meeting.user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if is_user_inactive(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been disabled"
        )

    new_meeting = Meeting(
        user_id=meeting.user_id,
        title=meeting.title,
        description=meeting.description,
        meeting_date=meeting.meeting_date,
        location=meeting.location,
        duration=meeting.duration,
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

    update_data = meeting_update.model_dump(exclude_unset=True)
    if "participants" in update_data:
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
