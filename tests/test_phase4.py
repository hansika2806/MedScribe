"""
Phase 4 test script for PDF OCR, optional upload, and performance logs.

Run with:
    python tests/test_phase4.py

Start the backend first:
    python -m backend.main
"""

import json
import sys
from pathlib import Path

import requests


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

API_BASE_URL = "http://localhost:8000"
TEST_DIR = Path(__file__).parent
AUDIO_FILE = TEST_DIR / "test_consultation.wav"
PDF_FILE = TEST_DIR / "pdfs" / "sample_lab_report.pdf"
EXPECTED_NODES = {
    "transcribe",
    "clinical_relevance_filter",
    "clinical_extractor",
    "rag",
    "soap",
    "icd10",
    "qa_guardrail",
    "safety_guardrail",
}


def ensure_sample_pdf():
    if PDF_FILE.exists():
        return
    from create_sample_pdf import create_sample_report

    create_sample_report()


def require_server():
    print("\nChecking backend server...")
    response = requests.get(f"{API_BASE_URL}/health", timeout=5)
    response.raise_for_status()
    print("Backend server is healthy.")


def test_ocr_extraction():
    from backend.tools.ocr import process_pdf

    ensure_sample_pdf()
    result = process_pdf(str(PDF_FILE))
    lab_values = result.get("lab_values", {})

    print("\nOCR EXTRACTION")
    print(json.dumps(lab_values, indent=2))

    assert result.get("status") == "success", result
    assert "HbA1c" in lab_values
    assert any("Glucose" in key for key in lab_values), lab_values
    assert "Cholesterol_Total" in lab_values
    return result


def test_api_with_pdf():
    print("\nStarting API test with PDF. This can take several minutes on first model load.")
    require_server()
    ensure_sample_pdf()

    print("Uploading audio + PDF to /consultation...")
    with open(AUDIO_FILE, "rb") as audio, open(PDF_FILE, "rb") as pdf:
        response = requests.post(
            f"{API_BASE_URL}/consultation",
            files={
                "audio_file": ("test_consultation.wav", audio, "audio/wav"),
                "pdf_file": ("sample_lab_report.pdf", pdf, "application/pdf"),
            },
            timeout=300,
        )

    if response.status_code >= 400:
        print("\nAPI WITH PDF ERROR")
        print(response.text)
    response.raise_for_status()
    result = response.json()
    labs = result.get("extracted_lab_values", {})
    objective = result.get("soap_note", {}).get("objective", {}).get("content", "")

    print("\nAPI WITH PDF")
    print(f"Session: {result.get('session_id')}")
    print(f"OCR method: {result.get('ocr_method')}")
    print(json.dumps(labs, indent=2))

    assert result.get("ocr_method") == "paddleocr"
    assert labs
    assert "HbA1c" in labs
    assert "8.2" in objective or labs["HbA1c"]["value"] == "8.2"
    return result


def test_api_without_pdf():
    print("\nStarting API test without PDF. This runs the full pipeline again.")
    require_server()

    print("Uploading audio only to /consultation...")
    with open(AUDIO_FILE, "rb") as audio:
        response = requests.post(
            f"{API_BASE_URL}/consultation",
            files={"audio_file": ("test_consultation.wav", audio, "audio/wav")},
            timeout=300,
        )

    if response.status_code >= 400:
        print("\nAPI WITHOUT PDF ERROR")
        print(response.text)
    response.raise_for_status()
    result = response.json()

    print("\nAPI WITHOUT PDF")
    print(f"Session: {result.get('session_id')}")
    print(f"OCR method: {result.get('ocr_method')}")

    assert result.get("ocr_method") == "no_pdf"
    assert result.get("status") == "completed"
    return result


def test_performance_logging(session_id: str):
    response = requests.get(f"{API_BASE_URL}/performance/{session_id}", timeout=30)
    response.raise_for_status()
    records = response.json().get("records", [])
    node_records = [record for record in records if record.get("node")]
    logged_nodes = {record["node"] for record in node_records}

    print("\nPERFORMANCE LOGS")
    for record in node_records:
        print(
            f"{record['node']}: {record['status']} "
            f"{record['duration_seconds']}s "
            f"in={record.get('input_size', 0)} out={record.get('output_size', 0)}"
        )

    missing = EXPECTED_NODES - logged_nodes
    assert not missing, f"Missing node logs: {sorted(missing)}"
    return records


def main():
    if not AUDIO_FILE.exists():
        raise FileNotFoundError(f"Missing audio fixture: {AUDIO_FILE}")

    ocr_result = test_ocr_extraction()
    with_pdf = test_api_with_pdf()
    without_pdf = test_api_without_pdf()
    test_performance_logging(with_pdf["session_id"])

    print("\nPHASE 4 TEST SUMMARY")
    print(f"OCR values extracted: {len(ocr_result.get('lab_values', {}))}")
    print(f"With PDF session: {with_pdf['session_id']}")
    print(f"Without PDF session: {without_pdf['session_id']}")
    print("All Phase 4 checks passed.")


if __name__ == "__main__":
    main()
