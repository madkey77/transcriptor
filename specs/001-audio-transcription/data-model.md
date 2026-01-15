# Data Model: Audio Transcription with Speaker Diarization

**Phase**: 1 - Design & Contracts
**Date**: 2026-01-14
**Purpose**: Define data structures, relationships, and validation rules

## Entity Overview

The system manages two primary entities:
1. **Transcription** - Metadata about a processed audio file
2. **TranscriptionSegment** - Individual speech segments with speaker attribution

## Entity: Transcription

Represents a single transcription session from audio upload through completion.

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | UUID | Primary key, auto-generated | Unique identifier for the transcription |
| filename | String(255) | Not null | Original uploaded filename |
| file_size | Integer | Not null, > 0, ≤ 262,144,000 (250MB) | File size in bytes |
| upload_timestamp | DateTime | Not null, defaults to now() | When file was uploaded |
| status | Enum | Not null, one of: pending, processing, completed, failed | Current processing state |
| error_message | String(1000) | Nullable | User-friendly error description if status=failed |
| created_at | DateTime | Not null, defaults to now() | Record creation timestamp |
| updated_at | DateTime | Not null, auto-updated | Last modification timestamp |

### Validation Rules

- **filename**: Must have valid audio extension (.mp3, .wav, .m4a, .ogg, .flac)
- **file_size**: 0 < file_size ≤ 250MB (262,144,000 bytes)
- **status**: Transitions only allowed in this order:
  - pending → processing
  - processing → completed
  - processing → failed
  - No transitions from completed or failed (immutable once done)
- **error_message**: Required if status=failed, null otherwise

### State Transitions

```
        upload
          ↓
      [pending]
          ↓
     start processing
          ↓
    [processing]
       ↙      ↘
  success    failure
     ↓          ↓
[completed]  [failed]
```

### Business Rules

- Transcription ID must be returned immediately upon upload (before processing starts)
- Status must be queryable at any time without blocking
- Completed transcriptions are never deleted automatically (user's responsibility)
- Failed transcriptions retain error_message for debugging

## Entity: TranscriptionSegment

Represents a single speech segment within a transcription, attributed to a speaker.

### Attributes

| Attribute | Type | Constraints | Description |
|-----------|------|-------------|-------------|
| id | Integer | Primary key, auto-generated | Unique segment identifier |
| transcription_id | UUID | Foreign key to Transcription, not null, on delete cascade | Parent transcription |
| speaker_label | String(50) | Not null | System-assigned speaker ID (e.g., "SPEAKER_00") |
| custom_speaker_name | String(100) | Nullable | User-edited speaker name (e.g., "John") |
| text | Text | Not null | Transcribed text for this segment |
| start_time | Float | Not null, ≥ 0 | Segment start time in seconds |
| end_time | Float | Not null, > start_time | Segment end time in seconds |
| segment_order | Integer | Not null, ≥ 0 | Sequential order within transcription |

### Validation Rules

- **transcription_id**: Must reference existing Transcription
- **speaker_label**: Format must be "SPEAKER_XX" where XX is 00-99
- **custom_speaker_name**: If provided, must be 1-100 characters, no special characters except spaces, hyphens, apostrophes
- **text**: Must not be empty string
- **start_time**: Must be ≥ 0
- **end_time**: Must be > start_time (segments have non-zero duration)
- **segment_order**: Must be unique within a transcription, starts at 0

### Relationships

- **Many-to-One** with Transcription: A transcription has many segments, a segment belongs to one transcription
- **Cascade delete**: When a transcription is deleted, all its segments are deleted
- **Ordering**: Segments are ordered by segment_order for consistent display

### Business Rules

- Segments must be stored in chronological order (segment_order matches time order)
- Custom speaker names apply retroactively to all segments with the same speaker_label within a transcription
- Segments are immutable after creation except for custom_speaker_name field
- Display logic: Use custom_speaker_name if present, otherwise speaker_label

## Derived Data Structures

### TranscriptionWithSegments (API Response)

When fetching a complete transcription for display or download:

```typescript
{
  id: string,                    // UUID
  filename: string,
  file_size: number,
  upload_timestamp: string,      // ISO 8601
  status: "pending" | "processing" | "completed" | "failed",
  error_message: string | null,
  created_at: string,            // ISO 8601
  updated_at: string,            // ISO 8601
  segments: [
    {
      id: number,
      speaker: string,           // custom_speaker_name || speaker_label
      text: string,
      start_time: number,
      end_time: number,
      is_custom_name: boolean    // True if custom_speaker_name is set
    }
  ],
  speakers: [                    // Distinct speakers for editing UI
    {
      speaker_label: string,
      custom_speaker_name: string | null,
      segment_count: number
    }
  ]
}
```

### SpeakerUpdate (API Request)

When user edits a speaker name:

```typescript
{
  transcription_id: string,      // UUID
  speaker_label: string,         // Original system label
  custom_speaker_name: string    // New name (or null to reset)
}
```

## Database Schema (SQLAlchemy)

```python
from sqlalchemy import Column, String, Integer, Float, DateTime, Enum, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid
import enum

class TranscriptionStatus(enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Transcription(Base):
    __tablename__ = "transcriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(String(255), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    status = Column(Enum(TranscriptionStatus), nullable=False, default=TranscriptionStatus.PENDING)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship
    segments = relationship("TranscriptionSegment", back_populates="transcription", cascade="all, delete-orphan")

class TranscriptionSegment(Base):
    __tablename__ = "transcription_segments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transcription_id = Column(UUID(as_uuid=True), ForeignKey("transcriptions.id", ondelete="CASCADE"), nullable=False)
    speaker_label = Column(String(50), nullable=False)
    custom_speaker_name = Column(String(100), nullable=True)
    text = Column(Text, nullable=False)
    start_time = Column(Float, nullable=False)
    end_time = Column(Float, nullable=False)
    segment_order = Column(Integer, nullable=False)

    # Relationship
    transcription = relationship("Transcription", back_populates="segments")

    # Index for efficient ordering
    __table_args__ = (
        Index('ix_segments_transcription_order', 'transcription_id', 'segment_order'),
    )
```

## Data Access Patterns

### Create Transcription (on upload)

```python
# Initial creation with pending status
transcription = Transcription(
    filename=uploaded_file.filename,
    file_size=uploaded_file.size,
    status=TranscriptionStatus.PENDING
)
db.add(transcription)
db.commit()
return transcription.id
```

### Update Status (during processing)

```python
# Transition to processing
transcription.status = TranscriptionStatus.PROCESSING
db.commit()

# On success
transcription.status = TranscriptionStatus.COMPLETED
db.commit()

# On failure
transcription.status = TranscriptionStatus.FAILED
transcription.error_message = "Transcription failed: audio too noisy"
db.commit()
```

### Save Segments (after transcription completes)

```python
segments = []
for idx, segment_data in enumerate(whisperx_result):
    segment = TranscriptionSegment(
        transcription_id=transcription_id,
        speaker_label=segment_data["speaker"],
        text=segment_data["text"],
        start_time=segment_data["start"],
        end_time=segment_data["end"],
        segment_order=idx
    )
    segments.append(segment)

db.bulk_save_objects(segments)
db.commit()
```

### Fetch Transcription with Segments

```python
transcription = db.query(Transcription)\
    .options(joinedload(Transcription.segments))\
    .filter(Transcription.id == transcription_id)\
    .first()

# Segments automatically loaded via relationship
ordered_segments = sorted(transcription.segments, key=lambda s: s.segment_order)
```

### Update Speaker Name (user edit)

```python
# Update all segments with matching speaker_label
db.query(TranscriptionSegment)\
    .filter(
        TranscriptionSegment.transcription_id == transcription_id,
        TranscriptionSegment.speaker_label == speaker_label
    )\
    .update({"custom_speaker_name": new_name})
db.commit()
```

### List Transcription History

```python
transcriptions = db.query(Transcription)\
    .order_by(Transcription.created_at.desc())\
    .limit(100)\
    .all()

# Return without segments for performance
return [t.to_dict(include_segments=False) for t in transcriptions]
```

## Data Integrity Constraints

### Database-Level Constraints

```sql
-- Transcriptions table
ALTER TABLE transcriptions
  ADD CONSTRAINT check_file_size CHECK (file_size > 0 AND file_size <= 262144000),
  ADD CONSTRAINT check_status_error CHECK (
    (status = 'failed' AND error_message IS NOT NULL) OR
    (status != 'failed' AND error_message IS NULL)
  );

-- Transcription segments table
ALTER TABLE transcription_segments
  ADD CONSTRAINT check_time_range CHECK (end_time > start_time),
  ADD CONSTRAINT check_start_time CHECK (start_time >= 0),
  ADD CONSTRAINT unique_segment_order UNIQUE (transcription_id, segment_order);
```

### Application-Level Validation

```python
# Pydantic models for API validation
from pydantic import BaseModel, validator, Field

class TranscriptionCreate(BaseModel):
    filename: str = Field(..., max_length=255)
    file_size: int = Field(..., gt=0, le=262_144_000)

    @validator('filename')
    def validate_extension(cls, v):
        valid_exts = {'.mp3', '.wav', '.m4a', '.ogg', '.flac'}
        if not any(v.lower().endswith(ext) for ext in valid_exts):
            raise ValueError(f'Invalid file extension. Must be one of {valid_exts}')
        return v

class SpeakerNameUpdate(BaseModel):
    speaker_label: str = Field(..., regex=r'^SPEAKER_\d{2}$')
    custom_speaker_name: str | None = Field(None, min_length=1, max_length=100)

    @validator('custom_speaker_name')
    def validate_name(cls, v):
        if v and not v.replace(' ', '').replace('-', '').replace("'", '').isalnum():
            raise ValueError('Speaker name must contain only letters, numbers, spaces, hyphens, and apostrophes')
        return v
```

## Data Migration Strategy

### Initial Schema Creation

```bash
# Using Alembic (optional for personal project, can use Base.metadata.create_all())
alembic init migrations
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

### Future Schema Changes

- Add indexes if queries become slow (initially unnecessary)
- Add fields incrementally (e.g., language detection, confidence scores)
- Avoid breaking changes (add nullable columns, don't rename/delete)

## Summary

- **2 core entities**: Transcription (metadata), TranscriptionSegment (speech data)
- **Simple relationships**: One-to-many with cascade delete
- **State machine**: Clear status transitions for transcription lifecycle
- **Validation**: Database constraints + application-level checks
- **Optimized queries**: Indexed by transcription_id and segment_order
- **User edits**: Only custom_speaker_name is mutable post-processing
- **Minimal schema**: No premature optimization, extend as needed

This data model supports all functional requirements while maintaining simplicity per the constitution.
