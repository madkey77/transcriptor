from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from src.utils.validation import FileValidationError


class TranscriptionError(Exception):
    """Base exception for transcription-related errors."""

    def __init__(self, error_code: str, message: str, status_code: int = 500, details: str = None):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details
        super().__init__(message)


def setup_middleware(app: FastAPI) -> None:
    """Configure all middleware for the application."""

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://localhost:8000", "http://127.0.0.1:8000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Configure exception handlers for the application."""

    @app.exception_handler(FileValidationError)
    async def file_validation_error_handler(request: Request, exc: FileValidationError):
        return JSONResponse(
            status_code=400,
            content={
                "error_code": exc.error_code.value,
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(TranscriptionError)
    async def transcription_error_handler(request: Request, exc: TranscriptionError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
                "details": str(exc) if app.debug else None
            }
        )
