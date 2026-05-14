from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import SOAPNote, PopulationTag
import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

# SPECIFIC SYSTEM PROMPT FOR SOAP GENERATION
SOAP_SYSTEM_PROMPT = """ROLE:
You are the clinical documentation specialist for MedScribe, generating 
structured SOAP notes for hospital physicians in Indian hospital settings.

TASK:
Using extracted clinical entities, generate a complete SOAP note with full 
entity-level provenance.

S — SUBJECTIVE:
Patient-reported symptoms and duration.
Source: Patient turns from filtered transcript only.

O — OBJECTIVE:
Vitals and lab values.
If lab_values status is pending_manual_entry:
Write: "Lab values pending physician input."
Do not leave blank — document available vitals.
If any lab value carries unverified flag: include flag.

A — ASSESSMENT:
Clinical diagnosis based on S and O data.
List diagnosis names only (no ICD-10 codes yet - added in next node).

P — PLAN:
Treatment plan with guideline citations.
Using retrieved clinical guidelines, generate the Plan section with citations.
Include guideline source in format: [Source Year §Section]
Example: "Start metformin 500mg twice daily [ADA 2024 §9]"

CONFIDENCE SCORING:
Assign confidence score 0-1 to each section.
Below 0.85: list specific uncertain spans with reason.

PROVENANCE RECORD:
For every clinical entity in every section include:
- source: transcript / ocr / both
- speaker: Patient / Doctor / ocr_system
- utterance: exact original text
- verified: true / false
- confidence: entity-level score

OUTPUT FORMAT (JSON):
{
  "subjective": {
    "content": "Patient reports chest pain for 3 days, worsening when lying down.",
    "confidence": 0.92,
    "entities": [
      {
        "claim": "chest pain for 3 days",
        "source": "transcript",
        "speaker": "Patient",
        "utterance": "My chest has been hurting for 3 days",
        "verified": true,
        "confidence": 0.95
      }
    ],
    "uncertain_spans": []
  },
  "objective": {
    "content": "BP: 148/92 mmHg. HR: 88 bpm.",
    "confidence": 0.88,
    "entities": [
      {
        "claim": "BP: 148/92",
        "source": "transcript",
        "speaker": "Doctor",
        "utterance": "Your blood pressure is 148 over 92",
        "verified": true,
        "confidence": 0.95
      }
    ],
    "uncertain_spans": []
  },
  "assessment": {
    "content": "1. Type 2 Diabetes — uncontrolled\\n2. Essential Hypertension",
    "diagnoses": ["Type 2 Diabetes — uncontrolled", "Essential Hypertension"],
    "confidence": 0.90,
    "entities": [],
    "uncertain_spans": []
  },
  "plan": {
    "content": "1. Increase metformin to 1000mg twice daily.\\n2. Start lisinopril 10mg once daily.\\n3. Follow up in 2 weeks.",
    "guideline_citations": [],
    "confidence": 0.85,
    "entities": [
      {
        "claim": "metformin 1000mg twice daily",
        "source": "transcript",
        "speaker": "Doctor",
        "utterance": "Let's increase your metformin to 1000mg twice daily",
        "verified": true,
        "confidence": 0.90
      }
    ],
    "uncertain_spans": []
  }
}

CONSTRAINTS:
- All four sections mandatory — none can be empty
- Never fabricate data not present in input
- Every entity must carry full provenance record
- Do not fill sections with placeholder text
- If insufficient data for a section, note what's missing"""


def _to_plain_data(value: Any) -> Any:
    """
    Convert nested Pydantic models or plain dicts into JSON-serializable data.

    Some upstream entity collections, especially lab_values, may contain plain
    dict items instead of model instances. This keeps prompt construction
    resilient and avoids attribute errors during Phase 2 testing.
    """
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {k: _to_plain_data(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_plain_data(item) for item in value]
    return value


def extract_json_from_response(text: str):
    """
    Extract JSON object from LLM response using multiple methods.
    Handles markdown code fences, leading text, and trailing text.
    """
    import re

    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char == '{':
            try:
                obj, _ = decoder.raw_decode(text, i)
                return obj
            except (json.JSONDecodeError, ValueError):
                continue

    return None


def _normalize_uncertain_span(span: Any) -> dict[str, str]:
    """
    Normalize uncertain span output into the schema expected by Pydantic.

    The LLM sometimes returns plain strings or even entity-like dicts instead of
    {text, reason}. We coerce those shapes here rather than failing the request.
    """
    if isinstance(span, str):
        return {
            "text": span,
            "reason": "low_confidence"
        }

    if isinstance(span, dict):
        if "text" in span and "reason" in span:
            return {
                "text": str(span["text"]),
                "reason": str(span["reason"])
            }

        text = span.get("claim") or span.get("utterance") or span.get("content") or str(span)
        reason = span.get("reason") or "low_confidence"
        return {
            "text": str(text),
            "reason": str(reason)
        }

    return {
        "text": str(span),
        "reason": "low_confidence"
    }


def _normalize_guideline_citation(citation: Any) -> str:
    """
    Normalize guideline citations to plain strings.

    The LLM sometimes returns objects like {citation, source, relevance}
    instead of the List[str] required by the response schema.
    """
    if isinstance(citation, str):
        return citation

    if isinstance(citation, dict):
        return str(
            citation.get("citation")
            or citation.get("source")
            or citation.get("title")
            or citation
        )

    return str(citation)


def _get_section_alias(data: dict[str, Any], canonical_name: str) -> Any:
    """
    Fetch a SOAP section using forgiving aliases from LLM output.

    The model may return "Objective", "O", etc. We normalize those variants
    before validating the final SOAPNote object.
    """
    aliases = {
        "subjective": ["subjective", "Subjective", "S", "s"],
        "objective": ["objective", "Objective", "O", "o"],
        "assessment": ["assessment", "Assessment", "A", "a"],
        "plan": ["plan", "Plan", "P", "p"],
    }
    for alias in aliases[canonical_name]:
        if alias in data:
            return data[alias]
    return None


def _default_section(section_name: str) -> dict[str, Any]:
    """
    Build a fallback section so incomplete LLM output degrades to physician
    review instead of crashing the pipeline.
    """
    base = {
        "content": (
            f"{section_name.capitalize()} section could not be generated "
            "automatically. Physician review required."
        ),
        "confidence": 0.0,
        "entities": [],
        "uncertain_spans": [
            {
                "text": f"{section_name} section missing from model output",
                "reason": "generation_incomplete",
            }
        ],
    }

    if section_name == "assessment":
        base["diagnoses"] = []
    if section_name == "plan":
        base["guideline_citations"] = []

    return base


def _normalize_section(section_name: str, raw_section: Any) -> dict[str, Any]:
    """
    Normalize a single SOAP section into the schema expected by Pydantic.
    """
    if not isinstance(raw_section, dict):
        normalized = _default_section(section_name)
        if isinstance(raw_section, str) and raw_section.strip():
            normalized["content"] = raw_section.strip()
        return normalized

    normalized = _default_section(section_name)
    
    # Get content from raw section, but preserve it even if confidence is low
    # This is important for ICD-10 coding which needs the actual content
    raw_content = raw_section.get("content", "")
    if raw_content and raw_content.strip():
        normalized["content"] = str(raw_content)
    # Otherwise keep the default placeholder content

    confidence = raw_section.get("confidence", 0.0)
    try:
        normalized["confidence"] = float(confidence)
    except (TypeError, ValueError):
        normalized["confidence"] = 0.0

    entities = raw_section.get("entities", [])
    normalized["entities"] = entities if isinstance(entities, list) else []

    spans = raw_section.get("uncertain_spans", [])
    if not isinstance(spans, list):
        spans = [spans]
    normalized["uncertain_spans"] = [
        _normalize_uncertain_span(span)
        for span in spans
    ]

    if section_name == "assessment":
        diagnoses = raw_section.get("diagnoses", [])
        # Preserve diagnoses even if confidence is low - needed for ICD-10 coding
        if diagnoses and isinstance(diagnoses, list) and len(diagnoses) > 0:
            normalized["diagnoses"] = diagnoses
        else:
            normalized["diagnoses"] = []

    if section_name == "plan":
        citations = raw_section.get("guideline_citations", [])
        if not isinstance(citations, list):
            citations = [citations]
        normalized["guideline_citations"] = [
            _normalize_guideline_citation(citation)
            for citation in citations
        ]

    return normalized


def _normalize_soap_payload(soap_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize the full SOAP payload so incomplete or oddly keyed model output
    routes to QA review rather than crashing with a 500.
    """
    return {
        "subjective": _normalize_section(
            "subjective",
            _get_section_alias(soap_data, "subjective"),
        ),
        "objective": _normalize_section(
            "objective",
            _get_section_alias(soap_data, "objective"),
        ),
        "assessment": _normalize_section(
            "assessment",
            _get_section_alias(soap_data, "assessment"),
        ),
        "plan": _normalize_section(
            "plan",
            _get_section_alias(soap_data, "plan"),
        ),
    }


def soap_generator(state: PipelineState) -> PipelineState:
    """
    Node 11: SOAP Note Generator
    
    Runs AFTER Clinical Extractor and RAG.
    Generates structured SOAP note with provenance and guideline citations.
    """
    logger.info("=" * 80)
    logger.info("NODE 11: SOAP Generator")
    logger.info("=" * 80)
    
    entities = state.get("extracted_entities")
    if not entities:
        error_msg = "No extracted entities available for SOAP generation"
        logger.error(f"❌ {error_msg}")
        logger.error(f"State keys: {list(state.keys())}")
        state["error"] = error_msg
        return state
    
    logger.info(f"📝 Input entities:")
    logger.info(f"   Symptoms: {len(entities.symptoms)}")
    logger.info(f"   Medications: {len(entities.medications)}")
    logger.info(f"   Vitals: {len(entities.vitals)}")
    logger.info(f"   Lab values: {len(entities.lab_values)}")
    
    # Check if we have any meaningful data
    has_data = (
        len(entities.symptoms) > 0 or
        len(entities.medications) > 0 or
        len(entities.vitals) > 0 or
        len(entities.lab_values) > 0
    )
    
    if not has_data:
        logger.warning("⚠️ Extracted entities are empty - no clinical data to generate SOAP note")
        state["error"] = "No clinical data extracted from consultation"
        return state
    
    # Get retrieved guidelines
    guidelines = state.get("retrieved_guidelines", [])
    logger.info(f"   Retrieved guidelines: {len(guidelines)}")
    
    # Format entities for LLM
    entities_text = f"""
Symptoms: {json.dumps(_to_plain_data(entities.symptoms), indent=2)}
Medications: {json.dumps(_to_plain_data(entities.medications), indent=2)}
Vitals: {json.dumps(_to_plain_data(entities.vitals), indent=2)}
Lab Values: {json.dumps(_to_plain_data(entities.lab_values), indent=2)}
Family History: {json.dumps(_to_plain_data(entities.family_history), indent=2)}
Population Tag: {json.dumps(_to_plain_data(entities.population_tag), indent=2)}
"""
    
    # Format guidelines for LLM
    guidelines_text = ""
    if guidelines:
        guidelines_text = "\n\nRETRIEVED CLINICAL GUIDELINES:\n"
        for i, g in enumerate(guidelines[:5], 1):
            guidelines_text += f"\n{i}. {g['source']} (relevance: {g['relevance_score']})\n"
            guidelines_text += f"   Population: {g['population_match']}\n"
            guidelines_text += f"   {g['content'][:300]}...\n"
    
    user_prompt = f"""Clinical entities:
{entities_text}
{guidelines_text}

Please generate a complete SOAP note and output the JSON format specified."""
    
    # Call LLM
    llm = get_llm_service()
    try:
        logger.info("🤖 Calling LLM for SOAP note generation...")
        response_text = llm.generate(
            SOAP_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.1
        )
        soap_data = extract_json_from_response(response_text)

        if soap_data is None:
            logger.error("❌ Failed to extract JSON from SOAP LLM response")
            logger.error(f"Response (first 1000 chars): {response_text[:1000]}")
            state["error"] = (
                "JSON parse error in SOAP Generator: "
                "Failed to extract valid JSON from LLM response"
            )
            return state
        
        # Normalize section aliases, fill missing sections, and coerce nested fields
        soap_data = _normalize_soap_payload(soap_data)
        
        # Log diagnoses before creating SOAPNote
        diagnoses = soap_data['assessment'].get('diagnoses', [])
        logger.info(f"   Diagnoses extracted: {len(diagnoses)}")
        if diagnoses:
            logger.info(f"   Diagnoses list: {diagnoses}")
        
        state["soap_note"] = SOAPNote(**soap_data)
        
        logger.info(f"✅ SOAP note generated successfully")
        logger.info(f"   Confidence scores:")
        logger.info(f"      Subjective: {soap_data['subjective']['confidence']:.2f}")
        logger.info(f"      Objective: {soap_data['objective']['confidence']:.2f}")
        logger.info(f"      Assessment: {soap_data['assessment']['confidence']:.2f}")
        logger.info(f"      Plan: {soap_data['plan']['confidence']:.2f}")
        
        # Log content previews
        logger.info(f"   Content previews:")
        logger.info(f"      S: {soap_data['subjective']['content'][:80]}...")
        logger.info(f"      O: {soap_data['objective']['content'][:80]}...")
        logger.info(f"      A: {soap_data['assessment']['content'][:80]}...")
        logger.info(f"      P: {soap_data['plan']['content'][:80]}...")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse SOAP response as JSON: {e}")
        state["error"] = f"JSON parse error in SOAP Generator: {str(e)}"
    except Exception as e:
        logger.error(f"❌ Error in SOAP Generator: {e}")
        import traceback
        logger.error(traceback.format_exc())
        state["error"] = f"SOAP Generator error: {str(e)}"
    
    return state

# Made with Bob
