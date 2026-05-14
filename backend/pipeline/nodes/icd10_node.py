"""
ICD-10 Coding Node
Looks up ICD-10 codes for diagnoses and appends them to assessment
"""
import logging
from backend.pipeline.state import PipelineState
from backend.tools.icd10 import lookup_multiple_diagnoses

logger = logging.getLogger(__name__)


def icd10_node(state: PipelineState) -> PipelineState:
    """
    ICD-10 Node: Look up ICD-10 codes for diagnoses
    
    Input: soap_note.assessment.diagnoses
    Output: icd10_codes, updated assessment content
    """
    logger.info("Node 12: ICD-10 - Looking up diagnosis codes...")
    
    try:
        soap_note = state.get("soap_note")
        if not soap_note:
            logger.warning("No SOAP note found, skipping ICD-10 lookup")
            state["icd10_codes"] = []
            return state
        
        # Get diagnoses from assessment
        diagnoses = soap_note.assessment.diagnoses
        if not diagnoses:
            logger.info("No diagnoses to code")
            state["icd10_codes"] = []
            return state
        
        # Look up ICD-10 codes
        icd10_codes = lookup_multiple_diagnoses(diagnoses)
        state["icd10_codes"] = icd10_codes
        
        # Update assessment content to include ICD-10 codes
        updated_content = soap_note.assessment.content
        for code_info in icd10_codes:
            diagnosis = code_info["diagnosis"]
            code = code_info["code"]
            
            # Append ICD-10 code to diagnosis in content
            if diagnosis in updated_content and code != "PENDING":
                updated_content = updated_content.replace(
                    diagnosis,
                    f"{diagnosis} (ICD-10: {code})",
                    1  # Replace only first occurrence
                )
        
        # Update the assessment content
        soap_note.assessment.content = updated_content
        state["soap_note"] = soap_note
        
        logger.info(f"ICD-10 lookup complete: {len(icd10_codes)} codes")
        
    except Exception as e:
        logger.error(f"ICD-10 node failed: {e}")
        state["icd10_codes"] = []
        state["error"] = f"ICD-10 error: {str(e)}"
    
    return state


# Made with Bob