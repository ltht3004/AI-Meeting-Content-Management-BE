from pathlib import Path
from datetime import timezone
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.user import User
from app.schemas.recording import RecordingResponse
from app.services.storage import build_recording_storage_path, delete_file_from_storage, upload_file_to_storage

router = APIRouter()

ALLOWED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".ogg", ".opus", ".aac", ".flac"}
MAX_RECORDING_SIZE_BYTES = 50 * 1024 * 1024
MAX_RECORDING_SIZE_LABEL = "50MB"


def as_utc(value):
    if not value:
        return None

    if value.tzinfo:
        return value.astimezone(timezone.utc)

    return value.replace(tzinfo=timezone.utc)


def build_recording_response(recording: Recording) -> dict:
    return {
        "id": recording.id,
        "meeting_id": recording.meeting_id,
        "file_name": recording.file_name,
        "file_url": recording.file_url,
        "file_type": recording.file_type,
        "size": recording.size,
        "created_at": as_utc(recording.created_at),
        "updated_at": as_utc(recording.updated_at),
    }


def validate_recording_manager(db: Session, meeting: Meeting, current_user_id: Optional[str]) -> None:
    # Recording management is stricter than viewing: only meeting creator or admin can change files.
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Only the creator or an admin can manage recordings"
        )

    try:
        current_user_uuid = UUID(str(current_user_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid current user ID")

    current_user = db.query(User).filter(User.id == current_user_uuid).first()
    if not current_user:
        raise HTTPException(status_code=404, detail="User not found")

    is_admin = current_user.role == "admin"
    is_creator = meeting.user_id == current_user.id
    if not is_admin and not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Only the creator or an admin can manage recordings"
        )


@router.get("/meeting/{meeting_id}", response_model=list[RecordingResponse])
def get_recordings_by_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    recordings = db.query(Recording).filter(
        Recording.meeting_id == meeting_id
    ).order_by(
        Recording.created_at.desc()
    ).all()

    return [build_recording_response(recording) for recording in recordings]


@router.post("/upload/{meeting_id}", response_model=RecordingResponse)
async def upload_recording(
    meeting_id: UUID,
    file: UploadFile = File(...),
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID"),
    db: Session = Depends(get_db)
):
    meeting = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    validate_recording_manager(db, meeting, current_user_id)

    # Validate file type before reading content.
    # Browser MIME types can be inconsistent, so extension is the stable check here.
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only audio files are allowed (.mp3, .wav, .m4a, .ogg, .opus, .aac, .flac)"
        )

    # Reject oversized uploads early when the client provides file size.
    if file.size and file.size > MAX_RECORDING_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size must not exceed {MAX_RECORDING_SIZE_LABEL}."
        )

    # Generate a unique cloud filename while preserving the original extension.
    stored_name = f"{uuid4()}{extension}"

    contents = await file.read()

    # Reject empty files before uploading anything to cloud storage.
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty"
        )

    # Re-check size after reading because UploadFile.size may be missing for some clients.
    if len(contents) > MAX_RECORDING_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size must not exceed {MAX_RECORDING_SIZE_LABEL}."
        )

    # Upload binary audio to Supabase Storage; the database stores metadata and URL only.
    content_type = file.content_type or "audio/mpeg"
    storage_path = build_recording_storage_path(str(meeting_id), stored_name)
    file_url = upload_file_to_storage(
        contents=contents,
        object_path=storage_path,
        content_type=content_type
    )

    # Save recording metadata only after the cloud upload succeeds.
    recording = Recording(
        meeting_id=meeting_id,
        file_name=original_name,
        file_url=file_url,
        file_type=content_type,
        size=len(contents)
    )

    db.add(recording)
    db.commit()
    db.refresh(recording)

    return build_recording_response(recording)


@router.delete("/{recording_id}")
def delete_recording(
    recording_id: UUID,
    current_user_id: Optional[str] = Query(None, description="Current logged in user ID"),
    db: Session = Depends(get_db)
):
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(status_code=404, detail="Recording not found")

    meeting = db.query(Meeting).filter(Meeting.id == recording.meeting_id).first()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    validate_recording_manager(db, meeting, current_user_id)

    # Delete the cloud object before removing the database record to avoid orphaned files.
    delete_file_from_storage(recording.file_url)

    db.delete(recording)
    db.commit()

    return {"message": "Recording deleted successfully"}
