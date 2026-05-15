from fastapi import APIRouter, UploadFile, File, HTTPException, Body, Form
from backend.models.schemas import ConsultationResponse
from backend.pipeline.graph import get_pipeline
from backend.pipeline.state import PipelineState
from backend.monitoring import record_consultation_metrics, get_current_metrics
from backend.logging_config import get_performance_logger
from backend.tools.ocr import process_pdf
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
import uuid
import logging
from pathlib import Path
import time
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter()

TEMP_DIR = Path("data/temp")
TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _plain(value):
    """Convert Pydantic models to JSON-safe plain data."""
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _collect_provenance(soap_note) -> list[dict]:
    """Flatten SOAP section entities into persisted provenance records."""
    soap = _plain(soap_note)
    records = []
    for section in ["subjective", "objective", "assessment", "plan"]:
        for entity in soap.get(section, {}).get("entities", []) or []:
            entity["soap_section"] = section
            records.append(entity)
    return records


def _extract_lab_values(final_state: PipelineState) -> list[dict]:
    """Extract available lab values from pipeline entities for persistence."""
    extracted = final_state.get("extracted_entities")
    ocr_labs = final_state.get("test_report_values", {}) or {}
    seen = set()
    results = []
    if not extracted:
        for lab_name, lab_data in ocr_labs.items():
            if not isinstance(lab_data, dict):
                continue
            results.append({
                "lab_name": lab_name,
                "value": lab_data.get("value", ""),
                "unit": lab_data.get("unit", ""),
                "source": lab_data.get("source", "ocr"),
                "verified": lab_data.get("verified", True),
                "flag": lab_data.get("flag"),
            })
        return results
    lab_values = _plain(getattr(extracted, "lab_values", {}) or {})
    if not isinstance(lab_values, dict):
        lab_values = {}
    for lab_name, lab_data in lab_values.items():
        if not isinstance(lab_data, dict):
            continue
        seen.add(lab_name)
        results.append({
            "lab_name": lab_name,
            "value": lab_data.get("value", ""),
            "unit": lab_data.get("unit", ""),
            "source": lab_data.get("source", "transcript"),
            "verified": lab_data.get("verified", False),
            "flag": lab_data.get("flag"),
        })
    for lab_name, lab_data in ocr_labs.items():
        if lab_name in seen or not isinstance(lab_data, dict):
            continue
        results.append({
            "lab_name": lab_name,
            "value": lab_data.get("value", ""),
            "unit": lab_data.get("unit", ""),
            "source": lab_data.get("source", "ocr"),
            "verified": lab_data.get("verified", True),
            "flag": lab_data.get("flag"),
        })
    return results


def _persist_success(session_id: str, final_state: PipelineState, processing_time: float) -> None:
    """Persist all successful Phase 3 session artifacts."""
    soap_note = _plain(final_state["soap_note"])
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
    )
    save_soap_note(session_id, soap_note)
    save_diagnoses(session_id, _plain(icd10_codes))
    save_provenance(session_id, _collect_provenance(soap_note))
    save_guidelines(session_id, _plain(final_state.get("retrieved_guidelines", [])))
    save_qa_result(session_id, _plain(qa_result))
    save_safety_result(session_id, _plain(safety_result))
    if lab_values:
        save_lab_values(session_id, lab_values)


@router.post("/consultation", response_model=ConsultationResponse)
async def create_consultation(
    audio_file: UploadFile = File(...),
    pdf_file: Optional[UploadFile] = File(None),
    session_id: str | None = Form(default=None),
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
    audio_path = TEMP_DIR / f"{session_id}.wav"
    pdf_path = TEMP_DIR / f"{session_id}.pdf"
    
    try:
        save_consultation(session_id=session_id, status="processing")

        # Save uploaded audio file
        with open(audio_path, "wb") as f:
            content = await audio_file.read()
            f.write(content)
        
        logger.info(f"Processing consultation {session_id}, audio size: {len(content)} bytes")

        if pdf_file is not None:
            with open(pdf_path, "wb") as f:
                pdf_content = await pdf_file.read()
                f.write(pdf_content)
            logger.info(
                "Processing uploaded PDF for session %s, size: %s bytes",
                session_id,
                len(pdf_content),
            )
            ocr_result = process_pdf(str(pdf_path))
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
            "transcript_raw": None,
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
        pipeline = get_pipeline()
        final_state = pipeline.invoke(initial_state)
        
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
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Pipeline processing failed",
                    "error": str(final_state['error']),
                    "session_id": session_id
                }
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
            )
            raise HTTPException(
                status_code=500,
                detail={
                    "message": "Pipeline processing failed",
                    "error": "SOAP note generation failed - no output produced",
                    "session_id": session_id
                }
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

        _persist_success(session_id, final_state, processing_time)
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
        )
        
        # Record failure metrics
        record_consultation_metrics(
            success=False,
            processing_time=0.0,
            error=str(e)
        )
        
        raise HTTPException(
            status_code=500,
            detail={
                "message": "Pipeline processing failed",
                "error": str(e),
                "session_id": session_id
            }
        )
    finally:
        for path in [audio_path, pdf_path]:
            try:
                if path.exists():
                    path.unlink()
            except Exception as e:
                logger.warning("Failed to delete temp file %s: %s", path, e)


@router.get("/consultation/{session_id}", response_model=ConsultationResponse)
async def get_consultation(session_id: str):
    """
    Get full persisted consultation session for refresh restore
    """
    consultation = get_persisted_consultation(session_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    return consultation


@router.get("/consultation/{session_id}/status")
async def get_consultation_status(session_id: str):
    """Return minimal persisted status for polling."""
    consultation = get_persisted_consultation(session_id)
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

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
        raise HTTPException(status_code=404, detail="Consultation not found")
    update_lab_values(session_id, payload.get("lab_values", []))
    return {"status": "updated", "session_id": session_id}


@router.post("/consultation/{session_id}/approve")
async def approve_consultation_endpoint(
    session_id: str,
    payload: dict = Body(default={}),
):
    """Approve and finalize a consultation note."""
    if not get_persisted_consultation(session_id):
        raise HTTPException(status_code=404, detail="Consultation not found")
    result = approve_consultation(session_id)
    return {
        "status": result["status"],
        "approved_at": result["approved_at"],
        "session_id": session_id,
    }


@router.post("/consultation/{session_id}/retry")
async def retry_consultation(session_id: str):
    """Mark a failed session for future retry support."""
    if not get_persisted_consultation(session_id):
        raise HTTPException(status_code=404, detail="Consultation not found")
    return {"status": "retry_initiated", "session_id": session_id}


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "MedScribe API",
        "version": "0.4.0-phase4"
    }


@router.get("/metrics")
async def get_metrics():
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
        raise HTTPException(status_code=500, detail=str(e))


# Made with Bob
