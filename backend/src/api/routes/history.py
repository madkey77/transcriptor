from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from src.storage.database import get_db
from src.storage.repository import TranscriptionRepository
from src.utils.formatters import format_as_txt, format_as_json, format_as_srt

router = APIRouter(prefix="/api", tags=["history"])


class TranscriptionSummary(BaseModel):
    """Summary for history list."""
    id: str
    filename: str
    status: str
    created_at: str
    speaker_count: Optional[int] = None


class TranscriptionListResponse(BaseModel):
    """Response for history list."""
    total: int
    items: list[TranscriptionSummary]


@router.get("/history", response_model=TranscriptionListResponse)
async def get_history(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db)
):
    """List transcription history with pagination."""
    repo = TranscriptionRepository(db)
    items, total = repo.list_transcriptions(limit=limit, offset=offset)

    summaries = []
    for item in items:
        # Get speaker count for completed transcriptions
        speaker_count = None
        if item.status.value == "completed":
            speakers = item._get_speakers()
            speaker_count = len(speakers)

        summaries.append(TranscriptionSummary(
            id=item.id,
            filename=item.filename,
            status=item.status.value,
            created_at=item.created_at.isoformat(),
            speaker_count=speaker_count
        ))

    return TranscriptionListResponse(total=total, items=summaries)


@router.get("/transcribe/{transcription_id}/download")
async def download_transcription(
    transcription_id: str,
    format: str = Query(default="txt", regex="^(txt|json|srt)$"),
    db: Session = Depends(get_db)
):
    """Download transcription in specified format."""
    repo = TranscriptionRepository(db)
    transcription = repo.get_transcription(transcription_id)

    if not transcription:
        raise HTTPException(status_code=404, detail="Transcription not found")

    if transcription.status.value != "completed":
        raise HTTPException(
            status_code=400,
            detail="Transcription is not yet completed"
        )

    # Generate content based on format
    if format == "txt":
        content = format_as_txt(transcription)
        media_type = "text/plain"
        filename = f"{transcription.filename}.txt"
    elif format == "json":
        content = format_as_json(transcription)
        media_type = "application/json"
        filename = f"{transcription.filename}.json"
    elif format == "srt":
        content = format_as_srt(transcription)
        media_type = "application/x-subrip"
        filename = f"{transcription.filename}.srt"
    else:
        raise HTTPException(status_code=400, detail="Invalid format")

    return Response(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )
