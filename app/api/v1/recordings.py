from datetime import timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4
import urllib.request

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.meeting import Meeting
from app.models.recording import Recording
from app.models.transcript import Transcript
from app.models.user import User
from app.schemas.recording import RecordingResponse
from app.services.ai_transcribe import transcribe_audio
from app.services.storage import (
    build_recording_storage_path,
    delete_file_from_storage,
    upload_file_to_storage,
)

router = APIRouter()

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3",
    ".wav",
    ".m4a",
    ".ogg",
    ".opus",
    ".aac",
    ".flac",
}

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


def validate_recording_manager(
    db: Session,
    meeting: Meeting,
    current_user_id: Optional[str],
) -> None:
    # Recording management is stricter than viewing: only meeting creator or admin can change files.
    if not current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Only the creator or an admin can manage recordings",
        )

    try:
        current_user_uuid = UUID(str(current_user_id))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid current user ID",
        ) from exc

    current_user = (
        db.query(User)
        .filter(User.id == current_user_uuid)
        .first()
    )

    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    is_admin = current_user.role == "admin"
    is_creator = meeting.user_id == current_user.id

    if not is_admin and not is_creator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: Only the creator or an admin can manage recordings",
        )


@router.get(
    "/meeting/{meeting_id}",
    response_model=list[RecordingResponse],
)
def get_recordings_by_meeting(
    meeting_id: UUID,
    db: Session = Depends(get_db),
):
    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    recordings = (
        db.query(Recording)
        .filter(Recording.meeting_id == meeting_id)
        .order_by(Recording.created_at.desc())
        .all()
    )

    return [
        build_recording_response(recording)
        for recording in recordings
    ]


@router.post(
    "/upload/{meeting_id}",
    response_model=RecordingResponse,
)
async def upload_recording(
    meeting_id: UUID,
    file: UploadFile = File(...),
    current_user_id: Optional[str] = Query(
        None,
        description="Current logged in user ID",
    ),
    db: Session = Depends(get_db),
):
    print("RUNNING RECORDINGS.PY")

    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == meeting_id)
        .first()
    )

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    validate_recording_manager(
        db=db,
        meeting=meeting,
        current_user_id=current_user_id,
    )

    # Validate file type before reading content.
    # Browser MIME types can be inconsistent, so extension is the stable check here.
    original_name = Path(file.filename or "").name
    extension = Path(original_name).suffix.lower()

    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Only audio files are allowed "
                "(.mp3, .wav, .m4a, .ogg, .opus, .aac, .flac)"
            ),
        )

    # Reject oversized uploads early when the client provides file size.
    if file.size and file.size > MAX_RECORDING_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size must not exceed {MAX_RECORDING_SIZE_LABEL}.",
        )

    # Generate a unique cloud filename while preserving the original extension.
    stored_name = f"{uuid4()}{extension}"

    contents = await file.read()

    # Reject empty files before uploading anything to cloud storage.
    if not contents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    # Re-check size after reading because UploadFile.size may be missing for some clients.
    if len(contents) > MAX_RECORDING_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size must not exceed {MAX_RECORDING_SIZE_LABEL}.",
        )

    # Upload binary audio to Supabase Storage; the database stores metadata and URL only.
    content_type = file.content_type or "audio/mpeg"

    storage_path = build_recording_storage_path(
        str(meeting_id),
        stored_name,
    )

    file_url = upload_file_to_storage(
        contents=contents,
        object_path=storage_path,
        content_type=content_type,
    )

    # Save recording metadata only after the cloud upload succeeds.
    recording = Recording(
        meeting_id=meeting_id,
        file_name=original_name,
        file_url=file_url,
        file_type=content_type,
        size=len(contents),
    )

    db.add(recording)
    db.commit()
    db.refresh(recording)

    # Send the uploaded audio to Whisper and save the returned transcript.
    # If Whisper fails, the recording and cloud file remain saved for later processing.
    try:
        print("START TRANSCRIBING:", recording.id)

        transcription_result = await transcribe_audio(
            file_content=contents,
            file_name=original_name,
            content_type=content_type,
        )

        print("WHISPER RESULT:", transcription_result)

        transcript = Transcript(
            recording_id=recording.id,
            content=transcription_result["text"],
            language=transcription_result.get("language"),
        )

        db.add(transcript)
        db.commit()
        db.refresh(transcript)

        print("TRANSCRIPT SAVED:", transcript.id)

        # Generate and save AI Summary for the entire meeting
        try:
            print("START GENERATING SUMMARY FOR MEETING:", meeting_id)
            from app.services.ai_summary import summarize_transcript
            from app.models.summary import Summary

            # Fetch all transcripts for this meeting
            all_recordings = db.query(Recording).filter(Recording.meeting_id == meeting_id).all()
            recording_ids = [r.id for r in all_recordings]
            
            all_transcripts = db.query(Transcript).filter(Transcript.recording_id.in_(recording_ids)).all()
            
            # Combine transcript contents
            combined_content = "\n\n".join([t.content for t in all_transcripts if t.content])
            
            if combined_content:
                summary_text = await summarize_transcript(combined_content)
                
                # Check if a summary already exists
                existing_summary = db.query(Summary).filter(Summary.meeting_id == meeting_id).first()
                if existing_summary:
                    existing_summary.content = summary_text
                else:
                    new_summary = Summary(
                        meeting_id=meeting_id,
                        content=summary_text
                    )
                    db.add(new_summary)
                
                db.commit()
                print("SUMMARY GENERATED AND SAVED")
        except Exception as e:
            print(f"FAILED TO GENERATE SUMMARY: {str(e)}")
            # Do not rollback the transcript, just log the summary failure


    except RuntimeError as exc:
        # Roll back only the current failed transcript transaction.
        # The recording was committed previously, so it remains in the database.
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Recording was uploaded and saved successfully, "
                f"but transcription failed: {exc}"
            ),
        ) from exc

    return build_recording_response(recording)

@router.post("/{recording_id}/retry", response_model=RecordingResponse)
async def retry_transcription(
    recording_id: UUID,
    current_user_id: UUID = Query(...),
    db: Session = Depends(get_db)
):
    recording = db.query(Recording).filter(Recording.id == recording_id).first()
    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found."
        )

    meeting = db.query(Meeting).filter(Meeting.id == recording.meeting_id).first()
    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found."
        )

    # Check permission
    is_admin = False
    current_user = db.query(User).filter(User.id == current_user_id).first()
    if current_user and current_user.role == "admin":
        is_admin = True

    if not is_admin and meeting.creator_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only meeting creator or admin can retry transcription."
        )

    # Ensure transcript does not already exist
    existing_transcript = db.query(Transcript).filter(Transcript.recording_id == recording.id).first()
    if existing_transcript:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcription already exists for this recording."
        )

    try:
        # Download file from Supabase URL
        print("DOWNLOADING AUDIO FOR RETRY:", recording.file_url)
        # Using a custom request with a dummy User-Agent in case needed, but Supabase public bucket usually doesn't care
        req = urllib.request.Request(recording.file_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=120) as response:
            contents = response.read()

    except Exception as e:
        print("DOWNLOAD FAILED:", str(e))
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to download audio from cloud storage: {str(e)}"
        )

    try:
        print("START TRANSCRIBING (RETRY):", recording.id)

        transcription_result = await transcribe_audio(
            file_content=contents,
            file_name=recording.file_name,
            content_type=recording.file_type,
        )

        print("WHISPER RESULT (RETRY):", transcription_result)

        transcript = Transcript(
            recording_id=recording.id,
            content=transcription_result["text"],
            language=transcription_result.get("language"),
        )

        db.add(transcript)
        db.commit()
        db.refresh(transcript)

        print("TRANSCRIPT SAVED (RETRY):", transcript.id)

        # Generate and save AI Summary for the entire meeting
        try:
            print("START GENERATING SUMMARY FOR MEETING (RETRY):", meeting.id)
            from app.services.ai_summary import summarize_transcript
            from app.models.summary import Summary

            all_recordings = db.query(Recording).filter(Recording.meeting_id == meeting.id).all()
            recording_ids = [r.id for r in all_recordings]
            
            all_transcripts = db.query(Transcript).filter(Transcript.recording_id.in_(recording_ids)).all()
            
            combined_content = "\n\n".join([t.content for t in all_transcripts if t.content])
            
            if combined_content:
                summary_text = await summarize_transcript(combined_content)
                
                existing_summary = db.query(Summary).filter(Summary.meeting_id == meeting.id).first()
                if existing_summary:
                    existing_summary.content = summary_text
                else:
                    new_summary = Summary(
                        meeting_id=meeting.id,
                        content=summary_text
                    )
                    db.add(new_summary)
                
                db.commit()
                print("SUMMARY GENERATED AND SAVED (RETRY)")
        except Exception as e:
            print(f"FAILED TO GENERATE SUMMARY (RETRY): {str(e)}")

    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Transcription retry failed: {str(exc)}",
        ) from exc

    return build_recording_response(recording)


@router.get("/{recording_id}/transcript")
def get_transcript_by_recording(
    recording_id: UUID,
    db: Session = Depends(get_db),
):
    recording = (
        db.query(Recording)
        .filter(Recording.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found",
        )

    transcript = (
        db.query(Transcript)
        .filter(Transcript.recording_id == recording_id)
        .first()
    )

    if not transcript:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not found",
        )

    return {
        "id": transcript.id,
        "recording_id": transcript.recording_id,
        "content": transcript.content,
        "language": transcript.language,
        "created_at": as_utc(transcript.created_at),
        "updated_at": as_utc(transcript.updated_at),
    }
    
@router.delete("/{recording_id}")
def delete_recording(
    recording_id: UUID,
    current_user_id: Optional[str] = Query(
        None,
        description="Current logged in user ID",
    ),
    db: Session = Depends(get_db),
):
    recording = (
        db.query(Recording)
        .filter(Recording.id == recording_id)
        .first()
    )

    if not recording:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recording not found",
        )

    meeting = (
        db.query(Meeting)
        .filter(Meeting.id == recording.meeting_id)
        .first()
    )

    if not meeting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    validate_recording_manager(
        db=db,
        meeting=meeting,
        current_user_id=current_user_id,
    )

    # Delete the cloud object before removing the database record to avoid orphaned files.
    delete_file_from_storage(recording.file_url)

    db.delete(recording)
    db.commit()

    return {
        "message": "Recording deleted successfully",
    }