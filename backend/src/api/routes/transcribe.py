from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from sqlalchemy.orm import Session
import asyncio
import json
import re

from src.storage.database import get_db
from src.storage.repository import TranscriptionRepository
from src.storage.models import TranscriptionStatus
from src.utils.validation import validate_audio_file, FileValidationError
from src.transcription.progress import get_progress_manager

router = APIRouter(prefix="/api/transcribe", tags=["transcription"])


# Pydantic Schemas
class TranscriptionCreatedResponse(BaseModel):
    """Response when transcription is created."""
    id: str
    status: str
    filename: str
    position: int


class TranscriptionStatusResponse(BaseModel):
    """Response for status check."""
    id: str
    status: str
    current_stage: Optional[str] = None
    error_message: Optional[str] = None


class SegmentResponse(BaseModel):
    """Segment in transcription response."""
    id: int
    speaker: str
    speaker_label: str
    text: str
    start_time: float
    end_time: float
    is_custom_name: bool


class SpeakerResponse(BaseModel):
    """Speaker info in transcription response."""
    speaker_label: str
    custom_speaker_name: Optional[str] = None
    segment_count: int


class TranscriptionDetailResponse(BaseModel):
    """Full transcription response with segments."""
    id: str
    filename: str
    file_size: int
    upload_timestamp: str
    status: str
    error_message: Optional[str] = None
    created_at: str
    updated_at: str
    segments: list[SegmentResponse]
    speakers: list[SpeakerResponse]


class SpeakerUpdateRequest(BaseModel):
    """Request to update speaker name."""
    speaker_label: str = Field(..., pattern=r'^SPEAKER_\d{2}$')
    custom_speaker_name: Optional[str] = Field(None, min_length=1, max_length=100)

    @field_validator('custom_speaker_name')
    @classmethod
    def validate_speaker_name(cls, v):
        if v is None:
            return v
        # Allow letters, numbers, spaces, hyphens, apostrophes
        if not re.match(r"^[a-zA-Z0-9\s\-']+$", v):
            raise ValueError('Speaker name must contain only letters, numbers, spaces, hyphens, and apostrophes')
        return v


class SpeakerUpdateResponse(BaseModel):
    """Response after speaker name update."""
    success: bool
    updated_segments: int


@router.post("", response_model=TranscriptionCreatedResponse, status_code=202)
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """
    Upload an audio file for transcription with speaker diarization.

    The file is enqueued and processed serially.
    """
    from src.transcription.queue import get_queue, QueueFullError

    content = await file.read()
    file_size = len(content)
    validate_audio_file(file.filename, file_size, content)

    repo = TranscriptionRepository(db)
    transcription = repo.create_transcription(file.filename, file_size)

    queue = get_queue()
    try:
        position = queue.enqueue(transcription.id, content)
    except QueueFullError:
        # Roll back the DB row so it doesn't sit as a stale pending.
        repo.update_status(
            transcription.id,
            TranscriptionStatus.FAILED,
            error_message="Queue full"
        )
        raise HTTPException(status_code=429, detail="Queue full")

    return TranscriptionCreatedResponse(
        id=transcription.id,
        status=transcription.status.value,
        filename=transcription.filename,
        position=position,
    )


@router.get("/{transcription_id}/status", response_model=TranscriptionStatusResponse)
async def get_status(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Check the processing status of a transcription."""
    repo = TranscriptionRepository(db)
    status = repo.get_transcription_status(transcription_id)

    if not status:
        raise HTTPException(status_code=404, detail="Transcription not found")

    return TranscriptionStatusResponse(**status)


@router.get("/{transcription_id}/progress")
async def stream_progress(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Stream real-time progress updates via Server-Sent Events."""
    # Verify transcription exists
    repo = TranscriptionRepository(db)
    transcription = repo.get_transcription_status(transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # If already completed or failed, return immediately
    if transcription["status"] in ["completed", "failed"]:
        async def immediate_response():
            data = {
                "event": "status",
                "data": transcription
            }
            yield f"data: {json.dumps(data)}\n\n"
        return StreamingResponse(
            immediate_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    progress_manager = get_progress_manager()

    async def event_generator():
        # Send initial status
        yield f"data: {json.dumps({'event': 'connected', 'transcription_id': transcription_id})}\n\n"

        # Register for updates if processing
        queue = progress_manager.register(transcription_id)

        try:
            while True:
                event = await progress_manager.get_event(transcription_id, timeout=30.0)

                if event is None:
                    # Send keepalive
                    yield f": keepalive\n\n"
                    continue

                event_data = {
                    "event": event.event_type.value,
                    "timestamp": event.timestamp,
                    **event.data
                }
                yield f"data: {json.dumps(event_data)}\n\n"

                # End stream on complete or error
                if event.event_type.value in ["complete", "error"]:
                    break

        finally:
            progress_manager.unregister(transcription_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/{transcription_id}", response_model=TranscriptionDetailResponse)
async def get_transcription(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Retrieve a transcription with all segments and speakers."""
    repo = TranscriptionRepository(db)
    transcription = repo.get_transcription(transcription_id)

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    return TranscriptionDetailResponse(**transcription.to_dict())


@router.patch("/{transcription_id}/speakers", response_model=SpeakerUpdateResponse)
async def update_speaker_name(
    transcription_id: str,
    update: SpeakerUpdateRequest,
    db: Session = Depends(get_db)
):
    """Update a speaker's custom name across all segments."""
    repo = TranscriptionRepository(db)

    # Check if transcription exists
    transcription = repo.get_transcription(transcription_id)
    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    # Update speaker name
    count = repo.update_speaker_name(
        transcription_id,
        update.speaker_label,
        update.custom_speaker_name
    )

    return SpeakerUpdateResponse(
        success=True,
        updated_segments=count
    )


@router.get("/{transcription_id}/download")
async def download_transcription(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Download transcription as Markdown file."""
    repo = TranscriptionRepository(db)
    transcription = repo.get_transcription(transcription_id)

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    if transcription.status.value != "completed":
        raise HTTPException(status_code=400, detail="Transcription not completed")

    # Generate Markdown content
    md_lines = [
        f"# {transcription.filename}",
        "",
        f"*Transcribed on {transcription.created_at.strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        ""
    ]

    for segment in transcription.segments:
        speaker_name = segment.custom_speaker_name or segment.speaker_label
        timestamp = f"{int(segment.start_time // 60)}:{int(segment.start_time % 60):02d}"
        md_lines.append(f"**{speaker_name}** [{timestamp}]")
        md_lines.append("")
        md_lines.append(segment.text)
        md_lines.append("")

    markdown_content = "\n".join(md_lines)

    # Create safe filename
    safe_filename = re.sub(r'[^\w\s-]', '', transcription.filename.rsplit('.', 1)[0])
    safe_filename = re.sub(r'\s+', '_', safe_filename)

    return Response(
        content=markdown_content,
        media_type="text/markdown",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_filename}.md"'
        }
    )


@router.delete("/{transcription_id}", status_code=204)
async def cancel_transcription(
    transcription_id: str,
    db: Session = Depends(get_db)
):
    """Cancel a pending transcription. 409 if already processing/finished."""
    from src.transcription.queue import get_queue

    repo = TranscriptionRepository(db)
    status = repo.get_transcription_status(transcription_id)
    if status is None:
        raise HTTPException(status_code=404, detail="Not found")

    if status["status"] != "pending":
        raise HTTPException(status_code=409, detail="Job is not cancellable")

    queue = get_queue()
    if queue.is_active(transcription_id):
        raise HTTPException(status_code=409, detail="Job is active")
    if not queue.cancel(transcription_id):
        # Job already left the pending list — worker picked it up between the
        # DB read and here. Don't mark FAILED; the running job will finish.
        raise HTTPException(status_code=409, detail="Job is no longer cancellable")

    repo.update_status(
        transcription_id,
        TranscriptionStatus.FAILED,
        error_message="Cancelled by user"
    )
    return Response(status_code=204)
