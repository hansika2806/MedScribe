"""
ICD-10 code lookup using NLM Clinical Tables API
Free API - no authentication required
"""
import logging
import requests
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# NLM ICD-10 API endpoint
ICD10_API_BASE = "https://clinicaltables.nlm.nih.gov/api/icd10cm/v3/search"


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
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": "Manual coding required - no match found"
        }
        
    except requests.exceptions.Timeout:
        logger.error(f"ICD-10 API timeout for: {diagnosis}")
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": "Manual coding required - API timeout"
        }
    except requests.exceptions.RequestException as e:
        logger.error(f"ICD-10 API error for '{diagnosis}': {e}")
        return {
            "diagnosis": diagnosis,
            "code": "PENDING",
            "description": f"Manual coding required - API error"
        }
    except Exception as e:
        logger.error(f"ICD-10 lookup failed for '{diagnosis}': {e}")
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