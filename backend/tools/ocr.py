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


class MedicalOCR:
    """Extract report text and common lab values from medical PDFs."""

    def __init__(self):
        self.ocr = None
        if PaddleOCR is not None:
            self.ocr = PaddleOCR(
                use_angle_cls=True,
                lang="en",
                use_gpu=False,
                show_log=False,
            )
            logger.info("PaddleOCR initialized successfully")
        else:
            logger.warning(
                "PaddleOCR dependencies are not installed; "
                "embedded PDF text fallback will be used when possible"
            )

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
        """Run PaddleOCR on a page image, with embedded text as fallback."""
        page_text: list[str] = []

        if self.ocr is not None and np is not None and Image is not None:
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
            img_array = np.array(image)

            result = self.ocr.ocr(img_array, cls=True)
            if result and result[0]:
                for line in result[0]:
                    if line and len(line) >= 2:
                        text = line[1][0]
                        confidence = line[1][1]
                        if confidence > 0.7:
                            page_text.append(text)

        if page_text:
            return page_text

        embedded_text = page.get_text("text") or ""
        return [line.strip() for line in embedded_text.splitlines() if line.strip()]

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
                    lab_values[lab_name] = {
                        "value": match.group(1),
                        "source": "ocr",
                        "verified": True,
                        "flag": None,
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
