"""
QA Guardrail Node
Checks SOAP note quality using LLM-based validation
"""
import logging
import json
from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """You are a clinical documentation quality assurance agent.
Check the SOAP note for these five failure modes and return a JSON result.

FAILURE MODE 1 - MISSING FIELDS:
Are all four SOAP sections (subjective, objective, assessment, plan) present and non-empty?

FAILURE MODE 2 - POPULATION MISMATCH:
Does the plan cite guidelines appropriate for the patient population? Check population_tag against guideline sources.

FAILURE MODE 3 - LOW CONFIDENCE:
Is any section confidence score below 0.85?

FAILURE MODE 4 - UNDOCUMENTED ENTITIES:
Are all extracted symptoms in the Subjective section?
Are all extracted medications in the Plan section?
Are all extracted vitals in the Objective section?

FAILURE MODE 5 - PROVENANCE INTEGRITY:
Does every clinical entity have source, speaker, utterance, and verified fields?

Return ONLY valid JSON:
{
  "overall_confidence": 0.X,
  "section_scores": {
    "subjective": 0.X,
    "objective": 0.X,
    "assessment": 0.X,
    "plan": 0.X
  },
  "flags": [
    {
      "failure_mode": "missing_field/population_mismatch/low_confidence/undocumented/provenance_integrity",
      "section": "subjective/objective/assessment/plan",
      "detail": "specific description of the issue"
    }
  ],
  "pass": true/false
}

pass = true ONLY if:
- All sections present and non-empty
- No population mismatch
- overall_confidence >= 0.85
- No undocumented entities
- All entities have provenance"""


def build_qa_prompt(state: PipelineState) -> str:
    """Build QA prompt with SOAP note and context"""
    try:
        soap_note = state.get("soap_note")
        extracted = state.get("extracted_entities")
        guidelines = state.get("retrieved_guidelines", [])
        
        if not soap_note:
            return ""
        
        # Build context
        prompt = "SOAP NOTE TO REVIEW:\n\n"
        
        # Add SOAP sections
        prompt += f"SUBJECTIVE (confidence: {soap_note.subjective.confidence}):\n"
        prompt += f"{soap_note.subjective.content}\n\n"
        
        prompt += f"OBJECTIVE (confidence: {soap_note.objective.confidence}):\n"
        prompt += f"{soap_note.objective.content}\n\n"
        
        prompt += f"ASSESSMENT (confidence: {soap_note.assessment.confidence}):\n"
        prompt += f"{soap_note.assessment.content}\n"
        prompt += f"Diagnoses: {', '.join(soap_note.assessment.diagnoses)}\n\n"
        
        prompt += f"PLAN (confidence: {soap_note.plan.confidence}):\n"
        prompt += f"{soap_note.plan.content}\n"
        prompt += f"Citations: {', '.join(soap_note.plan.guideline_citations)}\n\n"
        
        # Add extracted entities context
        if extracted:
            prompt += "EXTRACTED ENTITIES:\n"
            prompt += f"Population: {extracted.population_tag.age_group}, {extracted.population_tag.condition}\n"
            prompt += f"Symptoms: {', '.join([s.symptom for s in extracted.symptoms])}\n"
            prompt += f"Medications: {', '.join([m.drug for m in extracted.medications])}\n"
            prompt += f"Vitals: {', '.join(extracted.vitals.keys())}\n\n"
        
        # Add guideline sources
        if guidelines:
            prompt += "RETRIEVED GUIDELINES:\n"
            for g in guidelines[:3]:  # Top 3
                prompt += f"- {g['source']} (population: {g['population_match']})\n"
            prompt += "\n"
        
        prompt += "Perform QA check and return JSON result."
        
        return prompt
        
    except Exception as e:
        logger.error(f"Failed to build QA prompt: {e}")
        return ""


def qa_guardrail(state: PipelineState) -> PipelineState:
    """
    QA Guardrail Node: Validate SOAP note quality
    
    Input: soap_note, extracted_entities, retrieved_guidelines
    Output: qa_result
    """
    logger.info("Node 13: QA Guardrail - Validating SOAP note quality...")
    
    try:
        # Build prompt
        user_prompt = build_qa_prompt(state)
        if not user_prompt:
            logger.warning("Empty QA prompt, skipping validation")
            state["qa_result"] = {
                "overall_confidence": 0.0,
                "section_scores": {},
                "flags": [{"failure_mode": "missing_field", "section": "all", "detail": "No SOAP note to validate"}],
                "pass": False
            }
            return state
        
        # Call LLM
        llm = get_llm_service()
        qa_result = llm.generate_json(
            system_prompt=QA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=1000
        )
        
        # Validate result structure
        if "pass" not in qa_result:
            qa_result["pass"] = False
        if "overall_confidence" not in qa_result:
            qa_result["overall_confidence"] = 0.0
        if "flags" not in qa_result:
            qa_result["flags"] = []
        
        state["qa_result"] = qa_result
        
        logger.info(f"QA complete: pass={qa_result['pass']}, confidence={qa_result['overall_confidence']:.2f}, flags={len(qa_result['flags'])}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse QA JSON response: {e}")
        state["qa_result"] = {
            "overall_confidence": 0.0,
            "section_scores": {},
            "flags": [{"failure_mode": "low_confidence", "section": "all", "detail": "QA validation failed - JSON parse error"}],
            "pass": False
        }
    except Exception as e:
        logger.error(f"QA guardrail failed: {e}")
        state["qa_result"] = {
            "overall_confidence": 0.0,
            "section_scores": {},
            "flags": [{"failure_mode": "low_confidence", "section": "all", "detail": f"QA validation error: {str(e)}"}],
            "pass": False
        }
        state["error"] = f"QA error: {str(e)}"
    
    return state


# Made with Bob