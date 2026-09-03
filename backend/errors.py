from typing import Optional

from fastapi import HTTPException


ERROR_CODES = {
    "AUTH_EXPIRED": {
        "code": "AUTH_EXPIRED",
        "message": "Your session has expired. Please log in again.",
        "retryable": False,
        "http_status": 401,
    },
    "AUTH_INVALID": {
        "code": "AUTH_INVALID",
        "message": "Invalid credentials. Please check your username and password.",
        "retryable": False,
        "http_status": 401,
    },
    "GROQ_RATE_LIMIT": {
        "code": "GROQ_RATE_LIMIT",
        "message": "AI service is temporarily busy. Please wait a few minutes and try again.",
        "retryable": True,
        "http_status": 429,
    },
    "GROQ_API_ERROR": {
        "code": "GROQ_API_ERROR",
        "message": "AI service encountered an error. Please try again.",
        "retryable": True,
        "http_status": 500,
    },
    "WHISPER_FAILED": {
        "code": "WHISPER_FAILED",
        "message": "Audio transcription failed. Please check audio quality and try again.",
        "retryable": True,
        "http_status": 500,
    },
    "DIARIZATION_FAILED": {
        "code": "DIARIZATION_FAILED",
        "message": "Speaker identification failed. Fallback mode activated.",
        "retryable": False,
        "http_status": 200,
    },
    "OCR_FAILED": {
        "code": "OCR_FAILED",
        "message": "Could not read the PDF. Lab values will be marked as pending.",
        "retryable": False,
        "http_status": 200,
    },
    "NO_CLINICAL_CONTENT": {
        "code": "NO_CLINICAL_CONTENT",
        "message": "Could not extract clinical information from the audio. Please ensure the consultation was clearly recorded.",
        "retryable": True,
        "http_status": 500,
    },
    "PIPELINE_VALIDATION_ERROR": {
        "code": "PIPELINE_VALIDATION_ERROR",
        "message": "SOAP note could not be validated. Please try again.",
        "retryable": True,
        "http_status": 500,
    },
    "DATABASE_ERROR": {
        "code": "DATABASE_ERROR",
        "message": "Could not save consultation data. Please try again.",
        "retryable": True,
        "http_status": 500,
    },
    "UNKNOWN_ERROR": {
        "code": "UNKNOWN_ERROR",
        "message": "An unexpected error occurred. Please try again.",
        "retryable": True,
        "http_status": 500,
    },
}


def make_error_response(
    error_code: str,
    session_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> dict:
    error = ERROR_CODES.get(error_code, ERROR_CODES["UNKNOWN_ERROR"])
    return {
        "error_code": error["code"],
        "message": error["message"],
        "retryable": error["retryable"],
        "session_id": session_id,
        "detail": detail,
    }


def raise_standard_error(
    error_code: str,
    session_id: Optional[str] = None,
    detail: Optional[str] = None,
) -> None:
    error = ERROR_CODES.get(error_code, ERROR_CODES["UNKNOWN_ERROR"])
    raise HTTPException(
        status_code=error["http_status"],
        detail=make_error_response(error_code, session_id=session_id, detail=detail),
    )


def detect_error_code(exception_str: str) -> str:
    e = exception_str.lower()
    if "rate limit" in e or "429" in e:
        return "GROQ_RATE_LIMIT"
    if "groq" in e or "llm" in e:
        return "GROQ_API_ERROR"
    if "whisper" in e or "transcri" in e:
        return "WHISPER_FAILED"
    if "diariz" in e:
        return "DIARIZATION_FAILED"
    if "ocr" in e or "paddle" in e or "pdf" in e:
        return "OCR_FAILED"
    if "no extracted entities" in e or "no clinical" in e:
        return "NO_CLINICAL_CONTENT"
    if "validation" in e or "pydantic" in e:
        return "PIPELINE_VALIDATION_ERROR"
    if "database" in e or "sqlite" in e:
        return "DATABASE_ERROR"
    return "UNKNOWN_ERROR"
