"""CRUD helpers for persisted MedScribe consultation sessions."""

import json
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from backend.database.connection import get_connection, init_db


@contextmanager
def _db():
    init_db()
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat()


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _as_bool_int(value: Any) -> int:
    return 1 if bool(value) else 0


def save_consultation(
    session_id: str,
    status: str,
    review_type: Optional[str] = None,
    diarization_method: Optional[str] = None,
    processing_time_seconds: Optional[float] = None,
    error_message: Optional[str] = None,
) -> None:
    """Create or update a consultation row."""
    completed_at = _now() if status in {"completed", "failed"} else None
    with _db() as conn:
        existing = conn.execute(
            "SELECT id, created_at FROM consultations WHERE id = ?",
            (session_id,),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE consultations
                SET status = ?,
                    review_type = COALESCE(?, review_type),
                    diarization_method = COALESCE(?, diarization_method),
                    processing_time_seconds = COALESCE(?, processing_time_seconds),
                    error_message = ?,
                    completed_at = COALESCE(?, completed_at)
                WHERE id = ?
                """,
                (
                    status,
                    review_type,
                    diarization_method,
                    processing_time_seconds,
                    error_message,
                    completed_at,
                    session_id,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO consultations (
                    id, status, review_type, diarization_method,
                    processing_time_seconds, error_message, created_at, completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    status,
                    review_type,
                    diarization_method,
                    processing_time_seconds,
                    error_message,
                    _now(),
                    completed_at,
                ),
            )


def save_soap_note(session_id: str, soap_note_dict: Dict[str, Any]) -> None:
    """Persist the generated SOAP note section content and confidence scores."""
    soap = _plain(soap_note_dict)
    sections = ["subjective", "objective", "assessment", "plan"]
    scores = [float(soap.get(section, {}).get("confidence", 0.0) or 0.0) for section in sections]
    overall = sum(scores) / len(scores) if scores else 0.0
    with _db() as conn:
        conn.execute("DELETE FROM soap_notes WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO soap_notes (
                session_id,
                subjective_content, subjective_confidence,
                objective_content, objective_confidence,
                assessment_content, assessment_confidence,
                plan_content, plan_confidence,
                overall_confidence, approved, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """,
            (
                session_id,
                soap.get("subjective", {}).get("content", ""),
                scores[0],
                soap.get("objective", {}).get("content", ""),
                scores[1],
                soap.get("assessment", {}).get("content", ""),
                scores[2],
                soap.get("plan", {}).get("content", ""),
                scores[3],
                overall,
                _now(),
            ),
        )


def save_diagnoses(session_id: str, diagnoses_list: List[Dict[str, Any]]) -> None:
    """Persist diagnosis names and ICD-10 coding results."""
    with _db() as conn:
        conn.execute("DELETE FROM diagnoses WHERE session_id = ?", (session_id,))
        for item in _plain(diagnoses_list):
            code = item.get("code") or item.get("icd10_code") or "PENDING"
            status = "coded" if code and code != "PENDING" else "pending"
            conn.execute(
                """
                INSERT INTO diagnoses (
                    session_id, diagnosis_text, icd10_code,
                    icd10_description, status
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("diagnosis") or item.get("diagnosis_text", ""),
                    code,
                    item.get("description") or item.get("icd10_description", ""),
                    item.get("status") or status,
                ),
            )


def save_provenance(session_id: str, entities_list: List[Dict[str, Any]]) -> None:
    """Persist entity-level provenance records."""
    with _db() as conn:
        conn.execute("DELETE FROM provenance_records WHERE session_id = ?", (session_id,))
        for item in _plain(entities_list):
            conn.execute(
                """
                INSERT INTO provenance_records (
                    session_id, soap_section, claim, source, speaker,
                    utterance, verified, confidence
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("soap_section", ""),
                    item.get("claim", ""),
                    item.get("source", ""),
                    item.get("speaker", ""),
                    item.get("utterance", ""),
                    _as_bool_int(item.get("verified", False)),
                    float(item.get("confidence", 0.0) or 0.0),
                ),
            )


def save_guidelines(session_id: str, guidelines_list: List[Dict[str, Any]]) -> None:
    """Persist retrieved guideline snippets."""
    with _db() as conn:
        conn.execute("DELETE FROM retrieved_guidelines WHERE session_id = ?", (session_id,))
        for item in _plain(guidelines_list):
            conn.execute(
                """
                INSERT INTO retrieved_guidelines (
                    session_id, source, year, section, content,
                    relevance_score, population_match
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("source", ""),
                    str(item.get("year", "")),
                    item.get("section", ""),
                    item.get("content", ""),
                    float(item.get("relevance_score", 0.0) or 0.0),
                    item.get("population_match", ""),
                ),
            )


def save_qa_result(session_id: str, qa_result_dict: Dict[str, Any]) -> None:
    """Persist QA result and flags."""
    qa = _plain(qa_result_dict or {})
    section_scores = qa.get("section_scores", {}) or {}
    with _db() as conn:
        conn.execute("DELETE FROM qa_results WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO qa_results (
                session_id, overall_confidence, subjective_score,
                objective_score, assessment_score, plan_score,
                flags, passed
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                float(qa.get("overall_confidence", 0.0) or 0.0),
                float(section_scores.get("subjective", 0.0) or 0.0),
                float(section_scores.get("objective", 0.0) or 0.0),
                float(section_scores.get("assessment", 0.0) or 0.0),
                float(section_scores.get("plan", 0.0) or 0.0),
                json.dumps(qa.get("flags", [])),
                _as_bool_int(qa.get("pass", False)),
            ),
        )


def save_safety_result(session_id: str, safety_result_dict: Dict[str, Any]) -> None:
    """Persist clinical safety result and flags."""
    safety = _plain(safety_result_dict or {})
    with _db() as conn:
        conn.execute("DELETE FROM safety_results WHERE session_id = ?", (session_id,))
        conn.execute(
            """
            INSERT INTO safety_results (session_id, safety_pass, safety_flags)
            VALUES (?, ?, ?)
            """,
            (
                session_id,
                _as_bool_int(safety.get("safety_pass", True)),
                json.dumps(safety.get("safety_flags", [])),
            ),
        )


def save_lab_values(session_id: str, lab_values_list: List[Dict[str, Any]]) -> None:
    """Persist lab values."""
    with _db() as conn:
        for item in _plain(lab_values_list):
            conn.execute(
                """
                INSERT INTO lab_values (
                    session_id, lab_name, value, unit, source,
                    verified, flag, entered_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    item.get("lab_name") or item.get("name", ""),
                    item.get("value", ""),
                    item.get("unit", ""),
                    item.get("source", "manual_physician_entry"),
                    _as_bool_int(item.get("verified", False)),
                    item.get("flag"),
                    _now(),
                ),
            )


def update_lab_values(session_id: str, lab_values_list: List[Dict[str, Any]]) -> None:
    """Replace manually editable lab values for a session."""
    with _db() as conn:
        conn.execute("DELETE FROM lab_values WHERE session_id = ?", (session_id,))
    save_lab_values(session_id, lab_values_list)


def _fetch_all(conn, query: str, params: Iterable[Any]) -> List[Dict[str, Any]]:
    return [dict(row) for row in conn.execute(query, tuple(params)).fetchall()]


def get_consultation(session_id: str) -> Optional[Dict[str, Any]]:
    """Return a full persisted consultation response."""
    init_db()
    with get_connection() as conn:
        consultation = conn.execute(
            "SELECT * FROM consultations WHERE id = ?",
            (session_id,),
        ).fetchone()
        if not consultation:
            return None
        consultation_data = dict(consultation)

        soap = conn.execute(
            "SELECT * FROM soap_notes WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        diagnoses = _fetch_all(
            conn,
            "SELECT diagnosis_text, icd10_code, icd10_description, status FROM diagnoses WHERE session_id = ?",
            (session_id,),
        )
        provenance = _fetch_all(
            conn,
            "SELECT soap_section, claim, source, speaker, utterance, verified, confidence FROM provenance_records WHERE session_id = ?",
            (session_id,),
        )
        guidelines = _fetch_all(
            conn,
            "SELECT source, year, section, content, relevance_score, population_match FROM retrieved_guidelines WHERE session_id = ?",
            (session_id,),
        )
        qa = conn.execute(
            "SELECT * FROM qa_results WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        safety = conn.execute(
            "SELECT * FROM safety_results WHERE session_id = ? ORDER BY id DESC LIMIT 1",
            (session_id,),
        ).fetchone()
        labs = _fetch_all(
            conn,
            "SELECT lab_name, value, unit, source, verified, flag, entered_at FROM lab_values WHERE session_id = ?",
            (session_id,),
        )

    grouped_entities: Dict[str, List[Dict[str, Any]]] = {
        "subjective": [],
        "objective": [],
        "assessment": [],
        "plan": [],
    }
    for item in provenance:
        section = (item.pop("soap_section") or "").lower()
        if section in grouped_entities:
            item["verified"] = bool(item["verified"])
            grouped_entities[section].append(item)

    soap_note = None
    if soap:
        soap_dict = dict(soap)
        soap_note = {
            "subjective": {
                "content": soap_dict.get("subjective_content") or "",
                "confidence": soap_dict.get("subjective_confidence") or 0.0,
                "entities": grouped_entities["subjective"],
                "uncertain_spans": [],
            },
            "objective": {
                "content": soap_dict.get("objective_content") or "",
                "confidence": soap_dict.get("objective_confidence") or 0.0,
                "entities": grouped_entities["objective"],
                "uncertain_spans": [],
            },
            "assessment": {
                "content": soap_dict.get("assessment_content") or "",
                "confidence": soap_dict.get("assessment_confidence") or 0.0,
                "entities": grouped_entities["assessment"],
                "uncertain_spans": [],
                "diagnoses": [item["diagnosis_text"] for item in diagnoses],
            },
            "plan": {
                "content": soap_dict.get("plan_content") or "",
                "confidence": soap_dict.get("plan_confidence") or 0.0,
                "entities": grouped_entities["plan"],
                "uncertain_spans": [],
                "guideline_citations": [
                    f"{item['source']} {item['section']}".strip()
                    for item in guidelines
                    if item.get("source")
                ],
            },
        }

    qa_result = None
    if qa:
        qa_dict = dict(qa)
        qa_result = {
            "overall_confidence": qa_dict.get("overall_confidence") or 0.0,
            "section_scores": {
                "subjective": qa_dict.get("subjective_score") or 0.0,
                "objective": qa_dict.get("objective_score") or 0.0,
                "assessment": qa_dict.get("assessment_score") or 0.0,
                "plan": qa_dict.get("plan_score") or 0.0,
            },
            "flags": json.loads(qa_dict.get("flags") or "[]"),
            "pass": bool(qa_dict.get("passed")),
        }

    safety_result = None
    if safety:
        safety_dict = dict(safety)
        safety_result = {
            "safety_pass": bool(safety_dict.get("safety_pass")),
            "safety_flags": json.loads(safety_dict.get("safety_flags") or "[]"),
        }

    approved = bool(dict(soap).get("approved")) if soap else False
    approved_at = dict(soap).get("approved_at") if soap else None
    extracted_lab_values = {
        item["lab_name"]: {
            "value": item.get("value", ""),
            "unit": item.get("unit", ""),
            "source": item.get("source", "ocr"),
            "verified": bool(item.get("verified")),
            "flag": item.get("flag"),
        }
        for item in labs
        if item.get("source") in {"ocr", "ocr_only"}
    }

    return {
        "session_id": consultation_data["id"],
        "status": consultation_data.get("status") or "processing",
        "message": "SOAP note generated successfully" if soap_note else "Consultation is processing",
        "soap_note": soap_note,
        "retrieved_guidelines": guidelines,
        "qa_result": qa_result,
        "safety_result": safety_result,
        "requires_physician_review": True,
        "review_type": consultation_data.get("review_type"),
        "review_message": "",
        "diarization_method": consultation_data.get("diarization_method"),
        "ocr_method": "paddleocr" if extracted_lab_values else None,
        "ocr_page_count": None,
        "extracted_lab_values": extracted_lab_values,
        "processing_time": consultation_data.get("processing_time_seconds"),
        "icd10_codes": [
            {
                "diagnosis": item["diagnosis_text"],
                "code": item["icd10_code"],
                "description": item["icd10_description"],
                "status": item["status"],
            }
            for item in diagnoses
        ],
        "lab_values": labs,
        "approved": approved,
        "approved_at": approved_at,
        "created_at": consultation_data.get("created_at"),
        "completed_at": consultation_data.get("completed_at"),
        "error_message": consultation_data.get("error_message"),
    }


def approve_consultation(session_id: str) -> Dict[str, str]:
    """Mark the latest SOAP note for a consultation as approved."""
    approved_at = _now()
    with _db() as conn:
        conn.execute(
            """
            UPDATE soap_notes
            SET approved = 1, approved_at = ?
            WHERE session_id = ?
            """,
            (approved_at, session_id),
        )
    return {"status": "approved", "approved_at": approved_at}
