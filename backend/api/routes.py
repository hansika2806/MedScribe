from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Body, Form
from starlette.concurrency import run_in_threadpool
from backend.auth.dependency import get_current_physician
from backend.errors import ERROR_CODES, detect_error_code, make_error_response
from backend.models.schemas import ConsultationResponse
from backend.pipeline.state import PipelineState
from backend.monitoring import record_consultation_metrics, get_current_metrics
from backend.logging_config import get_performance_logger
from backend.utils import plain_dict, scrub_phi, validate_file_size
from backend.constants import (
    MAX_AUDIO_SIZE_BYTES,
    MAX_PDF_SIZE_BYTES,
    ALLOWED_AUDIO_TYPES,
    ALLOWED_PDF_TYPES,
)
from backend.database.repository import (
    approve_consultation,
    get_consultation as get_persisted_consultation,
    save_consultation,
    save_diagnoses,
    save_guidelines,
    save_lab_values,
    save_provenance,
    save_qa_result,
    save_safety_result,
    save_soap_note,
    update_lab_values,
)
import json
import uuid
import logging
from pathlib import Path
import time
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a", ".webm", ".ogg"}
AUDIO_EXTENSION_BY_CONTENT_TYPE = {
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/mpeg": ".mp3",
    "audio/mp3": ".mp3",
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/x-m4a": ".m4a",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}


def _safe_temp_stem(value: str) -> str:
    safe = "".join(
        char if char.isascii() and (char.isalnum() or char in {"-", "_"}) else "_"
        for char in value
    ).strip("_")
    return safe or str(uuid.uuid4())


def _audio_extension(upload: UploadFile) -> str:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix in AUDIO_EXTENSIONS:
        return suffix
    return AUDIO_EXTENSION_BY_CONTENT_TYPE.get(upload.content_type or "", ".wav")


def _parse_patient_context(raw_context: str | None) -> dict:
    if not raw_context:
        return {}
    try:
        parsed = json.loads(raw_context)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                detail=f"Invalid patient_context JSON: {exc.msg}",
            ),
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=400,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                detail="patient_context must be a JSON object",
            ),
        )
    allowed_keys = {"age", "gender", "allergies", "current_meds", "chief_complaint"}
    cleaned = {}
    for key, value in parsed.items():
        if key not in allowed_keys or value is None:
            continue
        text = str(value).strip()
        if text:
            cleaned[key] = text
    return cleaned


def _collect_provenance(soap_note) -> list[dict]:
    """
    Flatten SOAP section entities into persisted provenance records.
    
    Extracts all entities from each SOAP section (subjective, objective,
    assessment, plan) and adds the section name to each entity for tracking.
    
    Args:
        soap_note: SOAP note object (Pydantic model or dict) containing
                  sections with entities
    
    Returns:
        List of entity dictionaries with added 'soap_section' field
        
    Example:
        >>> soap = {"subjective": {"entities": [{"claim": "chest pain"}]}}
        >>> _collect_provenance(soap)
        [{"claim": "chest pain", "soap_section": "subjective"}]
    """
    soap = plain_dict(soap_note)
    records = []
    for section in ["subjective", "objective", "assessment", "plan"]:
        for entity in soap.get(section, {}).get("entities", []) or []:
            entity["soap_section"] = section
            records.append(entity)
    return records


def _extract_lab_values(final_state: PipelineState) -> list[dict]:
    """
    Extract available lab values from pipeline entities for persistence.
    
    Combines lab values from both transcript extraction and OCR processing,
    prioritizing transcript values when available and adding OCR values
    for any labs not found in the transcript.
    
    Args:
        final_state: Pipeline state containing extracted_entities and
                    test_report_values from OCR
    
    Returns:
        List of lab value dictionaries with fields:
        - lab_name: Name of the lab test
        - value: Measured value
        - unit: Unit of measurement
        - source: 'transcript' or 'ocr'
        - verified: Boolean indicating if value is verified
        - flag: Optional flag (e.g., 'high', 'low')
        
    Example:
        >>> state = {"extracted_entities": {"lab_values": {"HbA1c": {"value": "7.2"}}}}
        >>> _extract_lab_values(state)
        [{"lab_name": "HbA1c", "value": "7.2", "source": "transcript", ...}]
    """
    def build_lab_row(lab_name: str, lab_data: dict, default_source: str) -> dict:
        source = lab_data.get("source", default_source)
        value = lab_data.get("value", "")
        pdf_verified = source in {"ocr", "ocr_only", "both"} and bool(str(value).strip())
        return {
            "lab_name": lab_name,
            "value": value,
            "unit": lab_data.get("unit", ""),
            "source": "ocr_only" if source == "ocr" else source,
            "verified": True if pdf_verified else lab_data.get("verified", False),
            "flag": lab_data.get("flag"),
            "reference_range": lab_data.get("reference_range", ""),
            "display_name": lab_data.get("display_name", lab_name),
            "interpretation": lab_data.get("interpretation") or lab_data.get("flag") or "",
        }

    extracted = final_state.get("extracted_entities")
    ocr_labs = final_state.get("test_report_values", {}) or {}
    seen = set()
    results = []
    if not extracted:
        for lab_name, lab_data in ocr_labs.items():
            if not isinstance(lab_data, dict):
                continue
            results.append(build_lab_row(lab_name, lab_data, "ocr_only"))
        return results
    lab_values = plain_dict(getattr(extracted, "lab_values", {}) or {})
    if not isinstance(lab_values, dict):
        lab_values = {}
    for lab_name, lab_data in lab_values.items():
        if not isinstance(lab_data, dict):
            continue
        seen.add(lab_name)
        results.append(build_lab_row(lab_name, lab_data, "transcript"))
    for lab_name, lab_data in ocr_labs.items():
        if lab_name in seen or not isinstance(lab_data, dict):
            continue
        results.append(build_lab_row(lab_name, lab_data, "ocr_only"))
    return results


def _persist_success(
    session_id: str,
    final_state: PipelineState,
    processing_time: float,
    physician_username: str,
) -> None:
    """
    Persist all successful consultation session artifacts to database.
    
    Saves the complete consultation data including SOAP note, diagnoses,
    provenance records, guidelines, QA results, safety results, and lab values.
    
    Args:
        session_id: Unique identifier for the consultation session
        final_state: Complete pipeline state with all generated data
        processing_time: Total time taken to process consultation (seconds)
        physician_username: Username of the physician who initiated the consultation
        
    Returns:
        None - All data is persisted to SQLite database
        
    Raises:
        Database errors are propagated to caller for handling
        
    Side Effects:
        - Creates/updates consultation record
        - Saves SOAP note sections
        - Saves ICD-10 diagnoses
        - Saves provenance records for all entities
        - Saves retrieved clinical guidelines
        - Saves QA and safety check results
        - Saves lab values if present
    """
    soap_note = plain_dict(final_state.get("soap_note"))
    qa_result = final_state.get("qa_result", {})
    safety_result = final_state.get("safety_result", {})
    icd10_codes = final_state.get("icd10_codes", [])
    lab_values = _extract_lab_values(final_state)

    save_consultation(
        session_id=session_id,
        status="completed",
        review_type=final_state.get("review_type", "standard_approval"),
        diarization_method=final_state.get("diarization_method", "fallback"),
        processing_time_seconds=processing_time,
        error_message=None,
        physician_username=physician_username,
    )
    save_soap_note(session_id, soap_note)
    save_diagnoses(session_id, plain_dict(icd10_codes))
    save_provenance(session_id, _collect_provenance(soap_note))
    save_guidelines(session_id, plain_dict(final_state.get("retrieved_guidelines", [])))
    save_qa_result(session_id, plain_dict(qa_result))
    save_safety_result(session_id, plain_dict(safety_result))
    if lab_values:
        save_lab_values(session_id, lab_values)


@router.post("/consultation", response_model=ConsultationResponse)
async def create_consultation(
    audio_file: UploadFile = File(...),
    pdf_file: Optional[UploadFile] = File(None),
    session_id: str | None = Form(default=None),
    patient_context: str | None = Form(default=None),
    current_physician: dict = Depends(get_current_physician),
):
    """
    Process consultation audio and generate SOAP note
    
    Phase 4: Processes audio plus an optional PDF test report immediately.
    
    Args:
        audio_file: Audio file (WAV format recommended)
        pdf_file: Optional PDF lab/test report for OCR extraction
        
    Returns:
        ConsultationResponse with SOAP note or error
    """
    session_id = session_id or str(uuid.uuid4())
    start_time = time.time()
    ocr_method = "no_pdf"
    temp_stem = _safe_temp_stem(session_id)
    audio_path = TEMP_DIR / f"{temp_stem}{_audio_extension(audio_file)}"
    pdf_path = TEMP_DIR / f"{temp_stem}.pdf"
    parsed_patient_context = _parse_patient_context(patient_context)
    
    try:
        save_consultation(
            session_id=session_id,
            status="processing",
            patient_context=parsed_patient_context,
            physician_username=current_physician["username"],
        )

        # Validate and save uploaded audio file
        content = await audio_file.read()
        
        # Validate audio file size
        is_valid, error_msg = validate_file_size(len(content), MAX_AUDIO_SIZE_BYTES, "Audio")
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=make_error_response(
                    "UNKNOWN_ERROR",
                    session_id=session_id,
                    detail=error_msg,
                ),
            )
        
        # Validate audio content type
        if audio_file.content_type and audio_file.content_type not in ALLOWED_AUDIO_TYPES:
            logger.warning(f"Unexpected audio content type: {audio_file.content_type}")
        
        with open(audio_path, "wb") as f:
            f.write(content)
        
        logger.info(scrub_phi(f"Processing consultation {session_id}, audio size: {len(content)} bytes"))

        if pdf_file is not None:
            pdf_content = await pdf_file.read()
            
            # Validate PDF file size
            is_valid, error_msg = validate_file_size(len(pdf_content), MAX_PDF_SIZE_BYTES, "PDF")
            if not is_valid:
                raise HTTPException(
                    status_code=400,
                    detail=make_error_response(
                        "UNKNOWN_ERROR",
                        session_id=session_id,
                        detail=error_msg,
                    ),
                )
            
            # Validate PDF content type
            if pdf_file.content_type and pdf_file.content_type not in ALLOWED_PDF_TYPES:
                logger.warning(f"Unexpected PDF content type: {pdf_file.content_type}")
            
            with open(pdf_path, "wb") as f:
                f.write(pdf_content)
            logger.info(scrub_phi(
                f"Processing uploaded PDF for session {session_id}, size: {len(pdf_content)} bytes"
            ))
            # On Windows, PaddleOCR and faster-whisper can load conflicting native
            # runtimes. Initialize Whisper first so audio transcription remains stable.
            from backend.tools.whisper import get_transcriber
            from backend.tools.ocr import process_pdf

            await run_in_threadpool(get_transcriber)
            ocr_result = await run_in_threadpool(process_pdf, str(pdf_path))
            ocr_method = "paddleocr" if ocr_result.get("status") == "success" else "failed"
        else:
            ocr_result = {
                "test_values": "unavailable",
                "reason": "no_pdf_uploaded",
                "action": "physician_manual_entry",
                "lab_values": {},
                "status": "no_pdf",
                "page_count": 0,
            }
            ocr_method = "no_pdf"
        
        # Initialize state
        initial_state: PipelineState = {
            "audio_path": str(audio_path),
            "pdf_path": str(pdf_path) if pdf_file is not None else "",
            "ocr_result": ocr_result,
            "ocr_method": ocr_method,
            "test_report_values": ocr_result.get("lab_values", {}),
            "patient_context": parsed_patient_context,
            "transcript_raw": None,
            "transcript_segments": [],
            "transcript_diarized": None,
            "filtered_transcript": None,
            "extracted_entities": None,
            "soap_note": None,
            "session_id": session_id,
            "status": "processing",
            "error": None
        }
        
        # Run pipeline
        logger.info(f"Starting pipeline for session {session_id}")
        from backend.pipeline.graph import get_pipeline

        pipeline = get_pipeline()
        final_state = await run_in_threadpool(pipeline.invoke, initial_state)
        
        processing_time = time.time() - start_time
        
        # Check for errors
        if final_state.get("error"):
            logger.error(f"Pipeline error for session {session_id}: {final_state['error']}")
            get_performance_logger().log_session(
                session_id=session_id,
                total_duration=processing_time,
                review_type=final_state.get("review_type", "failed"),
                diarization_method=final_state.get("diarization_method", "fallback"),
                ocr_method=ocr_method,
                node_count=8,
                success=False,
            )
            save_consultation(
                session_id=session_id,
                status="failed",
                error_message=str(final_state["error"]),
                physician_username=current_physician["username"],
            )
            error_code = detect_error_code(str(final_state["error"]))
            raise HTTPException(
                status_code=ERROR_CODES[error_code]["http_status"],
                detail=make_error_response(
                    error_code,
                    session_id=session_id,
                    detail=str(final_state["error"]),
                ),
            )
        
        # Check if SOAP note was generated
        if not final_state.get("soap_note"):
            logger.error(f"No SOAP note generated for session {session_id}")
            get_performance_logger().log_session(
                session_id=session_id,
                total_duration=processing_time,
                review_type=final_state.get("review_type", "failed"),
                diarization_method=final_state.get("diarization_method", "fallback"),
                ocr_method=ocr_method,
                node_count=8,
                success=False,
            )
            save_consultation(
                session_id=session_id,
                status="failed",
                error_message="SOAP note generation failed - no output produced",
                physician_username=current_physician["username"],
            )
            error_code = "PIPELINE_VALIDATION_ERROR"
            raise HTTPException(
                status_code=ERROR_CODES[error_code]["http_status"],
                detail=make_error_response(
                    error_code,
                    session_id=session_id,
                    detail="SOAP note generation failed - no output produced",
                ),
            )
        
        # Clean up temp file
        try:
            audio_path.unlink()
            if pdf_path.exists():
                pdf_path.unlink()
        except Exception as e:
            logger.warning(f"Failed to delete temp file: {e}")
        
        logger.info(f"Consultation {session_id} completed in {processing_time:.2f}s")
        
        # Record metrics
        qa_result = final_state.get("qa_result", {})
        safety_result = final_state.get("safety_result", {})
        
        record_consultation_metrics(
            success=True,
            processing_time=processing_time,
            diarization_method=final_state.get("diarization_method", "fallback"),
            confidence=qa_result.get("overall_confidence", 0.0),
            safety_flags=len(safety_result.get("safety_flags", [])),
            qa_flags=len(qa_result.get("flags", [])),
            review_type=final_state.get("review_type", "standard_approval")
        )

        _persist_success(
            session_id,
            final_state,
            processing_time,
            current_physician["username"],
        )
        get_performance_logger().log_session(
            session_id=session_id,
            total_duration=processing_time,
            review_type=final_state.get("review_type", "standard_approval"),
            diarization_method=final_state.get("diarization_method", "fallback"),
            ocr_method=ocr_method,
            node_count=8,
            success=True,
        )
        
        # Build Phase 2 response
        response_data = {
            "session_id": session_id,
            "status": "completed",
            "message": "SOAP note generated successfully",
            "soap_note": final_state["soap_note"],
            "retrieved_guidelines": final_state.get("retrieved_guidelines", []),
            "icd10_codes": final_state.get("icd10_codes", []),
            "lab_values": _extract_lab_values(final_state),
            "qa_result": qa_result,
            "safety_result": safety_result,
            "requires_physician_review": final_state.get("requires_physician_review", True),
            "review_type": final_state.get("review_type", "standard_approval"),
            "review_message": final_state.get("review_message", ""),
            "diarization_method": final_state.get("diarization_method", "fallback"),
            "ocr_method": ocr_method,
            "ocr_page_count": ocr_result.get("page_count", 0),
            "extracted_lab_values": ocr_result.get("lab_values", {}),
            "processing_time": processing_time,
            "approved": False,
            "physician_username": current_physician["username"],
            "patient_context": parsed_patient_context,
        }
        
        return response_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing consultation: {e}", exc_info=True)
        processing_time = time.time() - start_time
        get_performance_logger().log_session(
            session_id=session_id,
            total_duration=processing_time,
            review_type="failed",
            diarization_method="fallback",
            ocr_method=ocr_method,
            node_count=8,
            success=False,
        )
        save_consultation(
            session_id=session_id,
            status="failed",
            error_message=str(e),
            physician_username=current_physician["username"],
        )
        
        # Record failure metrics
        record_consultation_metrics(
            success=False,
            processing_time=0.0,
            error=str(e)
        )
        error_code = detect_error_code(str(e))
        raise HTTPException(
            status_code=ERROR_CODES[error_code]["http_status"],
            detail=make_error_response(
                error_code,
                session_id=session_id,
                detail=str(e),
            ),
        )
    finally:
        for path in [audio_path, pdf_path]:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning("Failed to delete temp file %s: %s", path, e)


@router.get("/consultation/{session_id}", response_model=ConsultationResponse)
async def get_consultation(
    session_id: str,
    current_physician: dict = Depends(get_current_physician),
):
    """
    Get full persisted consultation session for refresh restore
    """
    consultation = get_persisted_consultation(session_id)
    if not consultation:
        raise HTTPException(
            status_code=404,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                session_id=session_id,
                detail="Consultation not found",
            ),
        )
    return consultation


@router.get("/consultation/{session_id}/status")
async def get_consultation_status(session_id: str):
    """Return minimal persisted status for polling."""
    consultation = get_persisted_consultation(session_id)
    if not consultation:
        raise HTTPException(
            status_code=404,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                session_id=session_id,
                detail="Consultation not found",
            ),
        )

    status = consultation.get("status", "processing")
    if status == "completed":
        current_node = "completed"
        progress = 100
    elif status == "failed":
        current_node = "failed"
        progress = 100
    else:
        current_node = "processing"
        progress = 10

    return {
        "session_id": session_id,
        "status": status,
        "current_node": current_node,
        "progress_percent": progress,
        "error_message": consultation.get("error_message"),
    }


@router.get("/performance/{session_id}")
async def get_performance(session_id: str):
    """Return structured performance records for a session."""
    return {
        "session_id": session_id,
        "records": get_performance_logger().get_session_stats(session_id),
    }


@router.post("/consultation/{session_id}/labs")
async def update_consultation_labs(
    session_id: str,
    payload: dict = Body(...),
):
    """Update lab values before physician approval."""
    if not get_persisted_consultation(session_id):
        raise HTTPException(
            status_code=404,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                session_id=session_id,
                detail="Consultation not found",
            ),
        )
    update_lab_values(session_id, payload.get("lab_values", []))
    return {"status": "updated", "session_id": session_id}


@router.post("/consultation/{session_id}/approve")
async def approve_consultation_endpoint(
    session_id: str,
    payload: dict = Body(default={}),
    current_physician: dict = Depends(get_current_physician),
):
    """Approve and finalize a consultation note."""
    if not get_persisted_consultation(session_id):
        raise HTTPException(
            status_code=404,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                session_id=session_id,
                detail="Consultation not found",
            ),
        )
    result = approve_consultation(
        session_id,
        physician_username=current_physician["username"],
        physician_name=current_physician["physician_name"],
    )
    return {
        "status": result["status"],
        "approved_at": result["approved_at"],
        "session_id": session_id,
        "approved_by": result["approved_by"],
        "physician_username": result["physician_username"],
    }


@router.post("/consultation/{session_id}/retry")
async def retry_consultation(session_id: str):
    """Mark a failed session for future retry support."""
    if not get_persisted_consultation(session_id):
        raise HTTPException(
            status_code=404,
            detail=make_error_response(
                "UNKNOWN_ERROR",
                session_id=session_id,
                detail="Consultation not found",
            ),
        )
    return {"status": "retry_initiated", "session_id": session_id}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MedScribe API",
        "version": "1.0.0-demo"
    }


@router.get("/metrics")
async def get_metrics(current_physician: dict = Depends(get_current_physician)):
    """
    Get current system metrics
    
    Returns metrics tracked across all consultations
    """
    try:
        metrics = get_current_metrics()
        return {
            "status": "success",
            "metrics": metrics
        }
    except Exception as e:
        logger.error(f"Failed to get metrics: {e}")
        error_code = detect_error_code(str(e))
        raise HTTPException(
            status_code=ERROR_CODES[error_code]["http_status"],
            detail=make_error_response(error_code, detail=str(e)),
        )


# Made with Bob
