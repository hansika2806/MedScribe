from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import ExtractedEntities, PopulationTag
import json
import logging

logger = logging.getLogger(__name__)


def extract_json_from_response(text: str):
    """
    Extract JSON object from LLM response using multiple methods.
    Handles markdown code fences, leading text, and trailing text.
    """
    import re
    
    # Method 1: Extract from markdown code fences
    match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    
    # Method 2: Find first { and use raw_decode
    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char == '{':
            try:
                obj, _ = decoder.raw_decode(text, i)
                return obj
            except (json.JSONDecodeError, ValueError):
                continue
    
    return None


# SPECIFIC SYSTEM PROMPT - NOT GENERIC
EXTRACTOR_SYSTEM_PROMPT = """ROLE:
You are the clinical NLP extraction agent for MedScribe, processing filtered
consultation transcripts in Indian hospital settings.

IMPORTANT: Return ONLY the JSON object. No explanation, no markdown code fences, no text before or after the JSON.

TASK:
From the filtered transcript, extract all clinically relevant entities with
full provenance for each entity.

1. SYMPTOMS — from Patient turns only
   Include symptom and duration.
   MUST include: source, speaker, utterance, verified fields

2. MEDICATIONS — from Doctor turns only
   Include drug name, dosage, frequency.
   MUST include: source, speaker, utterance fields

3. VITAL SIGNS — from Doctor turns
   Include BP, HR, temperature, SpO2.
   MUST include: source, speaker fields

4. LAB VALUES — from Doctor turns or OCR
   If lab_value has unverified flag: carry flag forward.
   If test_values unavailable: lab_values = {"status": "pending_manual_entry"}
   Never hallucinate any value.
   MUST include: source, verified, flag fields

5. FAMILY HISTORY — from Patient turns only
   Include condition and relation.
   MUST include: source, speaker fields

6. POPULATION TAG
   age_group: adult or pediatric
   condition: primary condition
   drug_class: primary medication category

OUTPUT FORMAT (JSON):
{
  "symptoms": [
    {
      "symptom": "chest pain",
      "duration": "3 days",
      "source": "transcript",
      "speaker": "Patient",
      "utterance": "My chest has been hurting for 3 days",
      "verified": true
    }
  ],
  "medications": [
    {
      "drug": "metformin",
      "dosage": "500mg",
      "frequency": "twice daily",
      "source": "transcript",
      "speaker": "Doctor",
      "utterance": "Continue metformin 500mg twice daily"
    }
  ],
  "vitals": {
    "BP": {
      "value": "148/92",
      "source": "transcript",
      "speaker": "Doctor"
    }
  },
  "lab_values": {
    "HbA1c": {
      "value": "8.2%",
      "source": "transcript_only",
      "verified": false,
      "flag": "verbally mentioned but not confirmed by test report"
    }
  },
  "family_history": [
    {
      "condition": "diabetes",
      "relation": "father",
      "source": "transcript",
      "speaker": "Patient"
    }
  ],
  "population_tag": {
    "age_group": "adult",
    "condition": "diabetes, hypertension",
    "drug_class": "antidiabetic"
  }
}

CONSTRAINTS:
- Extract only what was explicitly stated
- Symptoms from patient turns only — never doctor
- Prescriptions from doctor turns only — never patient
- Never fabricate lab values when OCR unavailable
- Every entity carries source, speaker, utterance reference
- Unverified verbal lab values carry their flag forward
- If no entities found in a category, return empty list/dict"""


def clinical_extractor(state: PipelineState) -> PipelineState:
    """
    Node 8: Clinical Extractor (Agent 2)
    
    Runs AFTER Clinical Relevance Filter.
    Extracts structured clinical entities with provenance.
    """
    logger.info("=" * 80)
    logger.info("NODE 8: Clinical Extractor")
    logger.info("=" * 80)
    
    filtered = state.get("filtered_transcript")
    if not filtered:
        error_msg = "No filtered transcript available for extraction"
        logger.error(f"❌ {error_msg}")
        logger.error(f"State keys: {list(state.keys())}")
        state["error"] = error_msg
        return state
    
    logger.info(f"📝 Input: {len(filtered.filtered_utterances)} filtered utterances")
    
    # Format filtered utterances for LLM
    included_utterances = [
        u for u in filtered.filtered_utterances if u.included
    ]
    
    logger.info(f"   Included utterances: {len(included_utterances)}")
    
    if not included_utterances:
        logger.warning("⚠️  No included utterances to extract from - returning empty entities")
        # Return empty entities
        state["extracted_entities"] = ExtractedEntities(
            symptoms=[],
            medications=[],
            vitals={},
            lab_values={},
            family_history=[],
            population_tag=PopulationTag(
                age_group="adult",
                condition="unknown",
                drug_class="none"
            )
        )
        return state
    
    utterances_text = "\n".join([
        f"[{u.speaker}] {u.utterance} (maps to: {u.maps_to})"
        for u in included_utterances
    ])
    
    logger.debug(f"Formatted utterances:\n{utterances_text[:500]}...")
    
    user_prompt = f"""Filtered transcript (clinically relevant utterances only):
{utterances_text}

OCR test values: Not available in Phase 1

Please extract clinical entities and output the JSON format specified."""
    
    # Call LLM
    llm = get_llm_service()
    try:
        logger.info("🤖 Calling LLM for clinical entity extraction...")
        
        # Use generate() instead of generate_json() for better error handling
        response_text = llm.generate(EXTRACTOR_SYSTEM_PROMPT, user_prompt, temperature=0.1)
        
        # Extract JSON using robust multi-method approach
        entities_data = extract_json_from_response(response_text)
        
        if entities_data is None:
            logger.error("❌ Failed to extract JSON from LLM response")
            logger.error(f"Response (first 1000 chars): {response_text[:1000]}")
            # Return empty entities on parse failure
            state["extracted_entities"] = ExtractedEntities(
                symptoms=[],
                medications=[],
                vitals={},
                lab_values={},
                family_history=[],
                population_tag=PopulationTag(
                    age_group="adult",
                    condition="unknown",
                    drug_class="none"
                )
            )
            state["error"] = "JSON parse error in extractor: Failed to extract valid JSON from LLM response"
            return state
        
        # Validate required fields
        required_fields = ["symptoms", "medications", "vitals", "lab_values", "family_history", "population_tag"]
        for field in required_fields:
            if field not in entities_data:
                logger.warning(f"⚠️  Response missing '{field}' field - adding empty value")
                if field == "population_tag":
                    entities_data[field] = {"age_group": "adult", "condition": "unknown", "drug_class": "none"}
                elif field in ["vitals", "lab_values"]:
                    entities_data[field] = {}
                else:
                    entities_data[field] = []
        
        # SANITIZE LLM OUTPUT before creating Pydantic objects
        
        # 1. Fix medications: replace None dosage/frequency with "unknown"
        if "medications" in entities_data:
            for med in entities_data["medications"]:
                if med.get("dosage") is None:
                    med["dosage"] = "unknown"
                if med.get("frequency") is None:
                    med["frequency"] = "unknown"
        
        # 2. Fix lab_values: if it's a dict with "status" string, convert to empty dict
        if "lab_values" in entities_data:
            lab_vals = entities_data["lab_values"]
            if isinstance(lab_vals, dict) and "status" in lab_vals and isinstance(lab_vals["status"], str):
                logger.info(f"   Lab values status: {lab_vals['status']}")
                entities_data["lab_values"] = {}
        
        # 3. Fix vitals: remove null entries the LLM sometimes emits for missing values
        if "vitals" in entities_data and isinstance(entities_data["vitals"], dict):
            cleaned_vitals = {}
            for vital_name, vital_value in entities_data["vitals"].items():
                if vital_value is None:
                    logger.info(f"   Removing null vital entry: {vital_name}")
                    continue
                cleaned_vitals[vital_name] = vital_value
            entities_data["vitals"] = cleaned_vitals
        
        # 4. Fix population_tag: if age_group is None, default to "adult"
        if "population_tag" in entities_data:
            pop_tag = entities_data["population_tag"]
            if pop_tag.get("age_group") is None:
                pop_tag["age_group"] = "adult"
        
        # Create ExtractedEntities object
        state["extracted_entities"] = ExtractedEntities(**entities_data)
        
        logger.info(f"✅ Extraction complete:")
        logger.info(f"   Symptoms: {len(entities_data.get('symptoms', []))}")
        logger.info(f"   Medications: {len(entities_data.get('medications', []))}")
        logger.info(f"   Vitals: {len(entities_data.get('vitals', {}))}")
        logger.info(f"   Lab values: {len(entities_data.get('lab_values', {}))}")
        logger.info(f"   Family history: {len(entities_data.get('family_history', []))}")
        
        # Log samples
        if entities_data.get('symptoms'):
            logger.info(f"   Sample symptom: {entities_data['symptoms'][0].get('symptom', 'N/A')}")
        if entities_data.get('medications'):
            logger.info(f"   Sample medication: {entities_data['medications'][0].get('drug', 'N/A')}")
        
    except Exception as e:
        logger.error(f"❌ Error in Clinical Extractor: {e}")
        import traceback
        logger.error(traceback.format_exc())
        state["error"] = f"Clinical Extractor error: {str(e)}"
    
    return state

# Made with Bob
