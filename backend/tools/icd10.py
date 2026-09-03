"""
ICD-10 code lookup using NLM Clinical Tables API
Free API - no authentication required
"""
import logging
import re
import requests
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# NLM ICD-10 API endpoint
ICD10_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"


def _normalize_diagnosis_text(diagnosis: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", diagnosis.lower()).strip()


def _fallback_result(diagnosis: str, code: str, description: str, reason: str) -> Dict[str, str]:
    return {
        "diagnosis": diagnosis,
        "code": code,
        "description": description,
        "status": "suggested_fallback",
        "source": "local_fallback",
        "confirmation_required": True,
        "reason": reason,
    }


def fallback_icd10_code(diagnosis: str) -> Optional[Dict[str, str]]:
    """
    Deterministic fallback mappings for common demo/clinical phrases that the
    remote ICD API often misses when wording includes modifiers.
    """
    normalized = _normalize_diagnosis_text(diagnosis)
    has_type_2_diabetes = (
        "type 2 diabetes" in normalized
        or "type ii diabetes" in normalized
        or "t2dm" in normalized
        or "diabetes mellitus type 2" in normalized
    )

    if has_type_2_diabetes and any(
        term in normalized
        for term in ["uncontrolled", "hyperglycemia", "hyperglycaemia", "high glucose", "elevated glucose", "poor control"]
    ):
        return _fallback_result(
            diagnosis,
            "E11.65",
            "Type 2 diabetes mellitus with hyperglycemia",
            "Type 2 diabetes wording includes uncontrolled or hyperglycemia modifier",
        )

    if has_type_2_diabetes:
        return _fallback_result(
            diagnosis,
            "E11.9",
            "Type 2 diabetes mellitus without complications",
            "Generic type 2 diabetes fallback",
        )

    if "essential hypertension" in normalized or normalized == "hypertension":
        return _fallback_result(
            diagnosis,
            "I10",
            "Essential (primary) hypertension",
            "Common hypertension fallback",
        )

    return None


def lookup_icd10_code(diagnosis: str) -> Dict[str, str]:
    """
    Look up ICD-10 code for a diagnosis using NLM API
    
    Args:
        diagnosis: Diagnosis string
        
    Returns:
        Dict with code and description
    """
    try:
        # Clean diagnosis string
        diagnosis_clean = diagnosis.strip()
        if not diagnosis_clean:
            return {
                "diagnosis": diagnosis,
                "code": "PENDING",
                "description": "Manual coding required - empty diagnosis"
            }

        fallback = fallback_icd10_code(diagnosis_clean)
        if fallback and fallback["code"] == "E11.65":
            logger.info("ICD-10 fallback: '%s' -> %s", diagnosis, fallback["code"])
            return fallback
        
        # Call NLM API
        params = {
            "sf": "code,name",
            "terms": diagnosis_clean,
            "maxList": 1
        }
        
        response = requests.get(ICD10_API_BASE, params=params, timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # Parse response: [[codes], total, [display], [code_name_pairs]]
        if len(data) >= 4 and data[3] and len(data[3]) > 0:
            code_name_pair = data[3][0]
            if len(code_name_pair) >= 2:
                code = code_name_pair[0]
                description = code_name_pair[1]
                
                logger.info(f"ICD-10 lookup: '{diagnosis}' -> {code}")
                return {
                    "diagnosis": diagnosis,
                    "code": code,
                    "description": description
                }
        
        # No match found
        logger.warning(f"No ICD-10 code found for: {diagnosis}")
        if fallback:
            logger.info("ICD-10 fallback after no match: '%s' -> %s", diagnosis, fallback["code"])
            return fallback
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": "Manual coding required - no match found"
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"ICD-10 API timeout for: {diagnosis}")
        fallback = fallback_icd10_code(diagnosis)
        if fallback:
            logger.info("ICD-10 fallback after timeout: '%s' -> %s", diagnosis, fallback["code"])
            return fallback
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": "Manual coding required - API timeout"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"ICD-10 API error for '{diagnosis}': {e}")
        fallback = fallback_icd10_code(diagnosis)
        if fallback:
            logger.info("ICD-10 fallback after API error: '%s' -> %s", diagnosis, fallback["code"])
            return fallback
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": f"Manual coding required - API error"
        }
    except Exception as e:
        logger.error(f"ICD-10 lookup failed for '{diagnosis}': {e}")
        fallback = fallback_icd10_code(diagnosis)
        if fallback:
            logger.info("ICD-10 fallback after lookup error: '%s' -> %s", diagnosis, fallback["code"])
            return fallback
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": "Manual coding required - lookup error"
        }


def lookup_multiple_diagnoses(diagnoses: List[str]) -> List[Dict[str, str]]:
    """
    Look up ICD-10 codes for multiple diagnoses
    
    Args:
        diagnoses: List of diagnosis strings
        
    Returns:
        List of dicts with code and description for each diagnosis
    """
    results = []
    for diagnosis in diagnoses:
        result = lookup_icd10_code(diagnosis)
        results.append(result)
    
    logger.info(f"ICD-10 lookup complete: {len(results)} diagnoses processed")
    return results


# Made with Bob
