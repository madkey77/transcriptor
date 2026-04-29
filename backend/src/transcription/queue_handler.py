"""Bridge between TranscriptionQueue (async) and AudioProcessor (sync)."""
import asyncio
import logging

from src.transcription.processor import get_audio_processor

logger = logging.getLogger(__name__)


async def queue_job_handler(transcription_id: str, content: bytes) -> None:
    """Run the synchronous AudioProcessor in a thread executor."""
    loop = asyncio.get_running_loop()
    processor = get_audio_processor()
    logger.info(f"Queue picked up job {transcription_id}")
    await loop.run_in_executor(None, processor.process, content, transcription_id)
