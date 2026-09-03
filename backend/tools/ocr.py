"""PDF OCR extraction for uploaded medical test reports."""

from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover - dependency installed in Phase 4 env
    fitz = None

try:
    import numpy as np
    from paddleocr import PaddleOCR
    from PIL import Image
except ImportError:  # pragma: no cover - allows app startup before install
    np = None
    PaddleOCR = None
    Image = None

logger = logging.getLogger(__name__)


LAB_METADATA = {
    "HbA1c": {
        "display_name": "HbA1c",
        "unit": "%",
        "reference_range": "Goal usually < 7.0% for many adults with diabetes",
        "high": 7.0,
    },
    "Blood_Glucose_Fasting": {
        "display_name": "Fasting glucose",
        "unit": "mg/dL",
        "reference_range": "70-99 mg/dL fasting; diabetes >= 126 mg/dL",
        "high": 125.0,
    },
    "Blood_Glucose_PP": {
        "display_name": "Post-prandial glucose",
        "unit": "mg/dL",
        "reference_range": "< 140 mg/dL 2-hour post-prandial",
        "high": 139.0,
    },
    "Blood_Glucose": {
        "display_name": "Blood glucose",
        "unit": "mg/dL",
        "reference_range": "Context dependent",
    },
    "Hemoglobin": {
        "display_name": "Hemoglobin",
        "unit": "g/dL",
        "reference_range": "Approx. 12-17 g/dL, varies by sex and lab",
    },
    "Creatinine": {
        "display_name": "Creatinine",
        "unit": "mg/dL",
        "reference_range": "Approx. 0.6-1.3 mg/dL",
        "high": 1.3,
    },
    "Cholesterol_Total": {
        "display_name": "Total cholesterol",
        "unit": "mg/dL",
        "reference_range": "< 200 mg/dL",
        "high": 199.0,
    },
    "HDL": {
        "display_name": "HDL cholesterol",
        "unit": "mg/dL",
        "reference_range": ">= 40 mg/dL; higher is generally protective",
        "low": 40.0,
    },
    "LDL": {
        "display_name": "LDL cholesterol",
        "unit": "mg/dL",
        "reference_range": "< 100 mg/dL for many high-risk adults",
        "high": 99.0,
    },
    "Triglycerides": {
        "display_name": "Triglycerides",
        "unit": "mg/dL",
        "reference_range": "< 150 mg/dL",
        "high": 149.0,
    },
    "Troponin_I": {
        "display_name": "Troponin I",
        "unit": "ng/mL",
        "reference_range": "Lab specific",
    },
    "CK_MB": {
        "display_name": "CK-MB",
        "unit": "ng/mL",
        "reference_range": "Lab specific",
    },
    "TSH": {
        "display_name": "TSH",
        "unit": "uIU/mL",
        "reference_range": "Approx. 0.4-4.0 uIU/mL",
    },
    "Free_T4": {
        "display_name": "Free T4",
        "unit": "ng/dL",
        "reference_range": "Lab specific",
    },
    "Insulin_Fasting": {
        "display_name": "Fasting insulin",
        "unit": "uIU/mL",
        "reference_range": "Lab specific",
    },
    "Sodium": {
        "display_name": "Sodium",
        "unit": "mEq/L",
        "reference_range": "135-145 mEq/L",
        "low": 135.0,
        "high": 145.0,
    },
    "Potassium": {
        "display_name": "Potassium",
        "unit": "mEq/L",
        "reference_range": "3.5-5.0 mEq/L",
        "low": 3.5,
        "high": 5.0,
    },
    "Urea": {
        "display_name": "Blood urea",
        "unit": "mg/dL",
        "reference_range": "Lab specific",
    },
    "eGFR": {
        "display_name": "eGFR",
        "unit": "mL/min/1.73m2",
        "reference_range": ">= 60 mL/min/1.73m2",
        "low": 60.0,
    },
    "WBC": {
        "display_name": "WBC",
        "unit": "10^3/uL",
        "reference_range": "Approx. 4.0-11.0 10^3/uL",
    },
    "Platelets": {
        "display_name": "Platelets",
        "unit": "10^3/uL",
        "reference_range": "Approx. 150-450 10^3/uL",
    },
    "Neutrophils": {
        "display_name": "Neutrophils",
        "unit": "%",
        "reference_range": "Lab specific",
    },
    "CRP": {
        "display_name": "CRP",
        "unit": "mg/L",
        "reference_range": "Lab specific",
    },
    "ESR": {
        "display_name": "ESR",
        "unit": "mm/hr",
        "reference_range": "Lab specific",
    },
    "Procalcitonin": {
        "display_name": "Procalcitonin",
        "unit": "ng/mL",
        "reference_range": "Lab specific",
    },
}


def _numeric_value(value: str) -> float | None:
    match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _interpret_lab_value(lab_name: str, value: str) -> str | None:
    metadata = LAB_METADATA.get(lab_name, {})
    numeric = _numeric_value(value)
    if numeric is None:
        return None

    high = metadata.get("high")
    low = metadata.get("low")
    if high is not None and numeric > float(high):
        return "high"
    if low is not None and numeric < float(low):
        return "low"
    return None


class MedicalOCR:
    """Extract report text and common lab values from medical PDFs."""

    def __init__(self):
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None and PaddleOCR is not None:
            try:
                self._ocr = PaddleOCR(
                    use_angle_cls=False,
                    lang="en",
                    use_gpu=False,
                    show_log=False,
                )
                logger.info("PaddleOCR initialized successfully")
            except Exception as e:
                logger.warning(f"PaddleOCR init failed: {e}")
                self._ocr = None
        return self._ocr

    def extract_from_pdf(self, pdf_path: str) -> dict:
        """
        Extract all text and lab values from all pages of a PDF file.

        Returns:
            dict with raw_text, lab_values, page_count, source, and status.
        """
        if fitz is None:
            return {
                "raw_text": "",
                "lab_values": {},
                "page_count": 0,
                "source": "ocr",
                "status": "failed",
                "error": "PyMuPDF is not installed",
            }

        doc = None
        try:
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            all_text: list[str] = []

            logger.info("Processing PDF: %s", pdf_path)
            logger.info("Total pages: %s", page_count)

            for page_num in range(page_count):
                page = doc.load_page(page_num)
                page_text = self._extract_page_text(page)
                all_text.extend(page_text)
                logger.info(
                    "Page %s: extracted %s lines",
                    page_num + 1,
                    len(page_text),
                )

            full_text = "\n".join(all_text)
            lab_values = self._extract_lab_values(full_text)

            logger.info("OCR complete. Extracted %s lab values", len(lab_values))

            return {
                "raw_text": full_text,
                "lab_values": lab_values,
                "page_count": page_count,
                "source": "ocr",
                "status": "success",
            }

        except Exception as e:
            logger.error("OCR extraction failed: %s", e)
            return {
                "raw_text": "",
                "lab_values": {},
                "page_count": 0,
                "source": "ocr",
                "status": "failed",
                "error": str(e),
            }
        finally:
            if doc is not None:
                doc.close()

    def _extract_page_text(self, page: Any) -> list[str]:
        """Extract page text: first check embedded digital text (fast, 0 MB RAM), then fallback to OCR."""
        embedded_text = page.get_text("text") or ""
        lines = [line.strip() for line in embedded_text.splitlines() if line.strip()]
        if lines:
            return lines

        page_text: list[str] = []
        ocr_engine = self._get_ocr()
        if ocr_engine is not None and np is not None and Image is not None:
            try:
                mat = fitz.Matrix(150 / 72, 150 / 72)
                pix = page.get_pixmap(matrix=mat)
                image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
                img_array = np.array(image)

                result = ocr_engine.ocr(img_array, cls=False)
                if result and result[0]:
                    for line in result[0]:
                        if line and len(line) >= 2:
                            text = line[1][0]
                            confidence = line[1][1]
                            if confidence > 0.7:
                                page_text.append(text)
            except Exception as e:
                logger.warning(f"OCR failed for page: {e}")

        return page_text

    def _extract_lab_values(self, text: str) -> dict:
        """
        Extract common lab values from OCR text using regex patterns for
        Indian medical reports.
        """
        lab_values = {}

        patterns = {
            "HbA1c": [
                r"HbA1c[^\d]{0,40}(\d+\.?\d*)\s*%?",
                r"Haemoglobin A1c[^\d]{0,40}(\d+\.?\d*)",
                r"Glycated Haemoglobin[^\d]{0,40}(\d+\.?\d*)",
                r"A1C[^\d]{0,40}(\d+\.?\d*)",
            ],
            "Blood_Glucose_Fasting": [
                r"Fasting\s+(?:Blood\s+)?Glucose[^\d]{0,80}(\d+\.?\d*)",
                r"Fasting\s+(?:Blood\s+)?G(?:l|I)ucose[^\d]{0,80}(\d+\.?\d*)",
                r"FBS[^\d]{0,40}(\d+\.?\d*)",
                r"Fasting\s+Sugar[^\d]{0,80}(\d+\.?\d*)",
            ],
            "Blood_Glucose_PP": [
                r"Post\s*Prandial\s*(?:Blood\s+)?Glucose[^\d]{0,80}(\d+\.?\d*)",
                r"Post\s*Prandial\s+Glucose[^\d]{0,80}(\d+\.?\d*)",
                r"PPBS[^\d]{0,40}(\d+\.?\d*)",
                r"2\s*Hour\s*PP[^\d]{0,40}(\d+\.?\d*)",
            ],
            "Blood_Glucose": [
                r"Blood\s+Glucose[^\d]{0,80}(\d+\.?\d*)",
            ],
            "Hemoglobin": [
                r"Haemoglobin[ \t:.-]{0,30}(\d+\.?\d*)\s*g?",
                r"Hemoglobin[ \t:.-]{0,30}(\d+\.?\d*)\s*g?",
                r"\bHb\b[ \t:.-]{0,30}(\d+\.?\d*)\s*g?",
            ],
            "Creatinine": [
                r"Creatinine[^\d]{0,80}(\d+\.?\d*)\s*mg?",
                r"Serum\s+Creatinine[^\d]{0,80}(\d+\.?\d*)",
                r"S\.?\s*Creatinine[^\d]{0,80}(\d+\.?\d*)",
            ],
            "Cholesterol_Total": [
                r"Total\s+Cholesterol[^\d]{0,80}(\d+\.?\d*)",
                r"Cholesterol[^\d]{0,80}(\d+\.?\d*)\s*mg?",
            ],
            "HDL": [
                r"HDL[^\d]{0,60}(\d+\.?\d*)",
                r"HDL\s+Cholesterol[^\d]{0,80}(\d+\.?\d*)",
            ],
            "LDL": [
                r"LDL[^\d]{0,60}(\d+\.?\d*)",
                r"LDL\s+Cholesterol[^\d]{0,80}(\d+\.?\d*)",
            ],
            "Triglycerides": [
                r"Triglycerides[^\d]{0,80}(\d+\.?\d*)",
                r"TG[^\d]{0,40}(\d+\.?\d*)",
            ],
            "Troponin_I": [
                r"Troponin\s+I\s*:?\s*(\d+\.?\d*)",
            ],
            "CK_MB": [
                r"CK-?MB\s*:?\s*(\d+\.?\d*)",
            ],
            "TSH": [
                r"TSH\s*:?\s*(\d+\.?\d*)",
                r"Thyroid\s+Stimulating\s+Hormone\s*:?\s*(\d+\.?\d*)",
            ],
            "Free_T4": [
                r"Free\s+T4\s*:?\s*(\d+\.?\d*)",
            ],
            "Insulin_Fasting": [
                r"Insulin\s+Fasting\s*:?\s*(\d+\.?\d*)",
            ],
            "Sodium": [
                r"Sodium\s*:?\s*(\d+\.?\d*)",
                r"Na\+?\s*:?\s*(\d+\.?\d*)\s*mEq",
            ],
            "Potassium": [
                r"Potassium\s*:?\s*(\d+\.?\d*)",
                r"K\+?\s*:?\s*(\d+\.?\d*)\s*mEq",
            ],
            "Urea": [
                r"Blood\s+Urea\s*:?\s*(\d+\.?\d*)",
                r"Urea\s*:?\s*(\d+\.?\d*)\s*mg",
            ],
            "eGFR": [
                r"eGFR\s*:?\s*(\d+\.?\d*)",
                r"GFR\s*:?\s*(\d+\.?\d*)",
            ],
            "WBC": [
                r"WBC\s*:?\s*(\d+\.?\d*)",
                r"White\s+Blood\s+Cell\s*:?\s*(\d+\.?\d*)",
            ],
            "Platelets": [
                r"Platelets\s*:?\s*(\d+\.?\d*)",
                r"PLT\s*:?\s*(\d+\.?\d*)",
            ],
            "Neutrophils": [
                r"Neutrophils\s*:?\s*(\d+\.?\d*)",
            ],
            "CRP": [
                r"CRP\s*:?\s*(\d+\.?\d*)",
            ],
            "ESR": [
                r"ESR\s*:?\s*(\d+\.?\d*)",
            ],
            "Procalcitonin": [
                r"Procalcitonin\s*:?\s*(\d+\.?\d*)",
            ],
        }

        for lab_name, pattern_list in patterns.items():
            for pattern in pattern_list:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    value = match.group(1)
                    metadata = LAB_METADATA.get(lab_name, {})
                    interpretation = _interpret_lab_value(lab_name, value)
                    lab_values[lab_name] = {
                        "value": value,
                        "source": "ocr",
                        "verified": True,
                        "flag": interpretation,
                        "interpretation": interpretation,
                        "unit": metadata.get("unit", ""),
                        "reference_range": metadata.get("reference_range", ""),
                        "display_name": metadata.get("display_name", lab_name.replace("_", " ")),
                    }
                    break

        return lab_values


_ocr_instance = None


def get_ocr() -> MedicalOCR:
    global _ocr_instance
    if _ocr_instance is None:
        _ocr_instance = MedicalOCR()
    return _ocr_instance


def process_pdf(pdf_path: str) -> dict:
    """Process a PDF and extract lab values for the pipeline."""
    if not Path(pdf_path).exists():
        return {
            "raw_text": "",
            "lab_values": {},
            "page_count": 0,
            "source": "ocr",
            "status": "failed",
            "error": f"PDF not found: {pdf_path}",
        }
    ocr = get_ocr()
    return ocr.extract_from_pdf(pdf_path)
