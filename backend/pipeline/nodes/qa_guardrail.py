"""
QA Guardrail Node
Checks SOAP note quality using compact LLM-based validation.
"""
import json
import logging

from backend.pipeline.state import PipelineState
from backend.services.llm import get_guardrail_llm

logger = logging.getLogger(__name__)

QA_SYSTEM_PROMPT = """You are a clinical documentation QA guardrail.
Review only the compact metrics provided. Return ONLY valid JSON:
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
      "section": "subjective/objective/assessment/plan/all",
      "detail": "specific description"
    }
  ],
  "pass": true/false
}

Fail if any section is missing, confidence is below 0.85, extracted entities are not represented, guideline population appears mismatched, or provenance is incomplete."""


def _get_val(obj, key, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _has_provenance(entity) -> bool:
    return all(
        _get_val(entity, field)
        for field in ("source", "speaker", "utterance")
    ) and _get_val(entity, "verified") is not None


def _count_mentions(items, text: str, field: str) -> int:
    text_lower = (text or "").lower()
    count = 0
    for item in items:
        value = str(_get_val(item, field, "") or "").lower()
        if value and value in text_lower:
            count += 1
    return count


def build_qa_prompt(state: PipelineState) -> str:
    """Build compact QA prompt with summary metrics only."""
    try:
        soap_note = state.get("soap_note")
        extracted = state.get("extracted_entities")
        guidelines = state.get("retrieved_guidelines", [])

        if not soap_note:
            return ""

        sections = ["subjective", "objective", "assessment", "plan"]
        section_scores = {}
        section_lengths = {}
        provenance_complete = True

        for section in sections:
            section_obj = _get_val(soap_note, section)
            content = _get_val(section_obj, "content", "") or ""
            confidence = _get_val(section_obj, "confidence", 0.0) or 0.0
            section_scores[section] = float(confidence)
            section_lengths[section] = len(content.strip())

            for entity in (_get_val(section_obj, "entities", []) or []):
                if not _has_provenance(entity):
                    provenance_complete = False
                    break

        subjective = _get_val(soap_note, "subjective")
        plan = _get_val(soap_note, "plan")
        subjective_content = _get_val(subjective, "content", "") or ""
        plan_content = _get_val(plan, "content", "") or ""

        symptoms = _get_val(extracted, "symptoms", []) if extracted else []
        medications = _get_val(extracted, "medications", []) if extracted else []
        population_tag = _get_val(extracted, "population_tag") if extracted else None
        age_group = _get_val(population_tag, "age_group", "unknown")
        condition = _get_val(population_tag, "condition", "unknown")

        symptom_count = len(symptoms or [])
        symptom_mentions = _count_mentions(symptoms or [], subjective_content, "symptom")
        medication_count = len(medications or [])
        medication_mentions = _count_mentions(medications or [], plan_content, "drug")

        guideline_summaries = []
        for guideline in guidelines[:3]:
            if isinstance(guideline, dict):
                guideline_summaries.append({
                    "source": guideline.get("source", "unknown"),
                    "population_match": guideline.get("population_match", ""),
                })

        summary = {
            "sections": {
                section: {
                    "confidence": section_scores[section],
                    "content_length": section_lengths[section],
                    "present": section_lengths[section] >= 10,
                }
                for section in sections
            },
            "entity_coverage": {
                "symptom_count": symptom_count,
                "subjective_mention_count": symptom_mentions,
                "medication_count": medication_count,
                "plan_mention_count": medication_mentions,
            },
            "population": {
                "age_group": age_group,
                "condition": condition,
                "guidelines": guideline_summaries,
            },
            "provenance_complete": provenance_complete,
        }

        return (
            "Evaluate this SOAP QA summary. Do not request full note text.\n"
            f"{json.dumps(summary, indent=2)}"
        )

    except Exception as e:
        logger.error(f"Failed to build QA prompt: {e}")
        return ""


def qa_guardrail(state: PipelineState) -> PipelineState:
    """
    QA Guardrail Node: Validate SOAP note quality.

    Input: soap_note, extracted_entities, retrieved_guidelines
    Output: qa_result
    """
    logger.info("Node 13: QA Guardrail - Validating SOAP note quality...")

    try:
        user_prompt = build_qa_prompt(state)
        if not user_prompt:
            logger.warning("Empty QA prompt, skipping validation")
            state["qa_result"] = {
                "overall_confidence": 0.0,
                "section_scores": {},
                "flags": [{
                    "failure_mode": "missing_field",
                    "section": "all",
                    "detail": "No SOAP note to validate",
                }],
                "pass": False,
            }
            return state

        llm = get_guardrail_llm()
        qa_result = llm.generate_json(
            system_prompt=QA_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            temperature=0.1,
            max_tokens=500,
        )

        if "pass" not in qa_result:
            qa_result["pass"] = False
        if "overall_confidence" not in qa_result:
            qa_result["overall_confidence"] = 0.0
        if "section_scores" not in qa_result:
            qa_result["section_scores"] = {}
        if "flags" not in qa_result:
            qa_result["flags"] = []

        state["qa_result"] = qa_result

        logger.info(
            f"QA complete: pass={qa_result['pass']}, "
            f"confidence={qa_result['overall_confidence']:.2f}, "
            f"flags={len(qa_result['flags'])}"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse QA JSON response: {e}")
        state["qa_result"] = {
            "overall_confidence": 0.0,
            "section_scores": {},
            "flags": [{
                "failure_mode": "low_confidence",
                "section": "all",
                "detail": "QA validation failed - JSON parse error",
            }],
            "pass": False,
        }
    except Exception as e:
        logger.error(f"QA guardrail failed: {e}")
        state["qa_result"] = {
            "overall_confidence": 0.0,
            "section_scores": {},
            "flags": [{
                "failure_mode": "low_confidence",
                "section": "all",
                "detail": f"QA validation error: {str(e)}",
            }],
            "pass": False,
        }
        state["error"] = f"QA error: {str(e)}"

    return state


# Made with Bob
