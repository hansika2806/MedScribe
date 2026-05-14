"""
Clinical Safety Guardrail Node
Checks for patient safety risks using LLM-based validation
"""
import logging
import json
from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service

logger = logging.getLogger(__name__)

SAFETY_SYSTEM_PROMPT = """You are a clinical safety agent. Check the SOAP note for patient safety risks. When in doubt, flag. False positives are acceptable. False negatives are not.

CHECK 1 - DANGEROUS DRUG COMBINATIONS:
Check medications list against these known interactions:
- warfarin + aspirin = increased bleeding risk
- SSRIs + MAOIs = serotonin syndrome (life threatening)
- metformin + contrast agents = lactic acidosis risk
- ACE inhibitors + potassium supplements = hyperkalemia
- NSAIDs + anticoagulants = bleeding risk
- fluoroquinolones + corticosteroids = tendon rupture
- digoxin + amiodarone = digoxin toxicity

CHECK 2 - RED FLAG DIAGNOSES:
Check assessment for these requiring immediate escalation:
- suspected MI or acute coronary syndrome → URGENT
- stroke or TIA indicators → URGENT
- sepsis indicators → URGENT
- acute respiratory failure → URGENT
- hypertensive emergency (BP above 180/120) → URGENT
- diabetic ketoacidosis → URGENT
- pulmonary embolism indicators → URGENT

CHECK 3 - DOSAGE RISK:
Flag medications with doses exceeding standard ranges:
- metformin above 2550mg/day in adults
- metformin above 2000mg/day in pediatric
- lisinopril above 40mg/day
- amlodipine above 10mg/day

Return ONLY valid JSON:
{
  "safety_pass": true/false,
  "safety_flags": [
    {
      "check_type": "drug_interaction/red_flag/dosage",
      "detail": "specific description",
      "urgency": "urgent/review"
    }
  ]
}

safety_pass = false if ANY flag exists."""


def build_safety_prompt(state: PipelineState) -> str:
    """Build safety check prompt with SOAP note"""
    try:
        soap_note = state.get("soap_note")
        extracted = state.get("extracted_entities")
        
        if not soap_note:
            return ""
        
        prompt = "SOAP NOTE TO CHECK FOR SAFETY RISKS:\n\n"
        
        # Add medications
        if extracted and extracted.medications:
            prompt += "MEDICATIONS:\n"
            for med in extracted.medications:
                dosage = med.dosage if med.dosage != "unknown" else "not specified"
                prompt += f"- {med.drug} ({dosage})\n"
            prompt += "\n"
        
        # Add vitals
        if extracted and extracted.vitals:
            prompt += "VITAL SIGNS:\n"
            for name, vital in extracted.vitals.items():
                prompt += f"- {name}: {vital.value}\n"
            prompt += "\n"
        
        # Add assessment
        prompt += f"ASSESSMENT:\n{soap_note.assessment.content}\n"
        prompt += f"Diagnoses: {', '.join(soap_note.assessment.diagnoses)}\n\n"
        
        # Add plan
        prompt += f"PLAN:\n{soap_note.plan.content}\n\n"
        
        # Add population context
        if extracted:
            prompt += f"PATIENT POPULATION: {extracted.population_tag.age_group}\n\n"
        
        prompt += "Perform safety check and return JSON result."
        
        return prompt
        
    except Exception as e:
        logger.error(f"Failed to build safety prompt: {e}")
        return ""


def safety_guardrail(state: PipelineState) -> PipelineState:
    """
    Safety Guardrail Node: Check for patient safety risks
    
    Input: soap_note, extracted_entities
    Output: safety_result
    """
    logger.info("Node 14: Safety Guardrail - Checking for safety risks...")
    
    try:
        # Build prompt
        user_prompt = build_safety_prompt(state)
        if not user_prompt:
            logger.warning("Empty safety prompt, skipping validation")
            state["safety_result"] = {
                "safety_pass": True,
                "safety_flags": []
            }
            return state
        
        # Call LLM
        llm = get_llm_service()
        safety_result = llm.generate_json(
            system_prompt=SAFETY_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1000
        )
        
        # Validate result structure
        if "safety_pass" not in safety_result:
            safety_result["safety_pass"] = True
        if "safety_flags" not in safety_result:
            safety_result["safety_flags"] = []
        
        state["safety_result"] = safety_result
        
        logger.info(f"Safety check complete: pass={safety_result['safety_pass']}, flags={len(safety_result['safety_flags'])}")
        
        # Log urgent flags
        urgent_flags = [f for f in safety_result["safety_flags"] if f.get("urgency") == "urgent"]
        if urgent_flags:
            logger.warning(f"⚠️ URGENT SAFETY FLAGS: {len(urgent_flags)}")
            for flag in urgent_flags:
                logger.warning(f"  - {flag.get('check_type')}: {flag.get('detail')}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse safety JSON response: {e}")
        state["safety_result"] = {
            "safety_pass": False,
            "safety_flags": [{
                "check_type": "system_error",
                "detail": "Safety validation failed - JSON parse error",
                "urgency": "review"
            }]
        }
    except Exception as e:
        logger.error(f"Safety guardrail failed: {e}")
        state["safety_result"] = {
            "safety_pass": False,
            "safety_flags": [{
                "check_type": "system_error",
                "detail": f"Safety validation error: {str(e)}",
                "urgency": "review"
            }]
        }
        state["error"] = f"Safety error: {str(e)}"
    
    return state


# Made with Bob