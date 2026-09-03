from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import FilteredTranscript
import json
import logging

logger = logging.getLogger(__name__)


def _plain(value):
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


def _extract_json_from_response(text: str):
    """Extract a JSON object from an LLM response with optional surrounding text."""
    import re

    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    decoder = json.JSONDecoder()
    for i, char in enumerate(text):
        if char == "{":
            try:
                obj, _ = decoder.raw_decode(text, i)
                return obj
            except (json.JSONDecodeError, ValueError):
                continue

    return None


def _normalize_speaker(speaker: str) -> str:
    """Normalize LLM speaker values to valid Pydantic literals.

    The LLM occasionally returns bracketed variants like '[uncertain]',
    '[Doctor]', '[Patient]', or unknown synonyms. Strip brackets and map
    everything that isn't an exact literal to 'uncertain'.
    """
    if not isinstance(speaker, str):
        return "uncertain"
    # Strip surrounding brackets, whitespace and quotes
    cleaned = speaker.strip().strip("[]\"'").strip()
    # Exact matches first
    if cleaned in {"Doctor", "Patient", "uncertain"}:
        return cleaned
    # Case-insensitive mapping for common variants
    lower = cleaned.lower()
    if lower in {"doctor", "physician", "dr", "dr."}:
        return "Doctor"
    if lower in {"patient", "pt"}:
        return "Patient"
    # Anything else is uncertain
    return "uncertain"


def _normalize_filter_payload(filtered_data: dict) -> dict:
    """Coerce common LLM shape drift before Pydantic validation."""
    if "filtered_utterances" not in filtered_data:
        for alias in ["filtered_transcript", "utterances", "results", "items"]:
            alias_value = filtered_data.get(alias)
            if isinstance(alias_value, dict) and "filtered_utterances" in alias_value:
                filtered_data = alias_value
                break
            if isinstance(alias_value, list):
                filtered_data["filtered_utterances"] = alias_value
                break

    filtered_data.setdefault("lab_value_verification", [])
    filtered_data.setdefault("utterances_excluded_count", 0)
    filtered_data.setdefault("speaker_uncertain_count", 0)

    # Normalize speaker values in every utterance so Pydantic doesn't reject
    # bracketed variants like '[uncertain]' returned by some LLMs.
    for utterance in filtered_data.get("filtered_utterances", []) or []:
        if isinstance(utterance, dict) and "speaker" in utterance:
            utterance["speaker"] = _normalize_speaker(utterance["speaker"])

    for item in filtered_data.get("lab_value_verification", []) or []:
        if item.get("source") == "ocr":
            item["source"] = "ocr_only"
        if item.get("source") not in {"both", "transcript_only", "ocr_only"}:
            item["source"] = "ocr_only" if item.get("verified") else "transcript_only"
    return filtered_data


def _map_utterance_to_section(speaker: str, text: str) -> str:
    text_lower = text.lower()
    if speaker == "Patient":
        return "Subjective"
    if any(word in text_lower for word in ["start", "prescribe", "increase", "continue", "refer", "follow up"]):
        return "Plan"
    if any(word in text_lower for word in ["diagnosis", "suggests", "rule out", "diabetes", "hypertension"]):
        return "Assessment"
    return "Objective"


def _fallback_filter_payload(transcript, test_report_values: dict) -> dict:
    """Build a conservative filter result if the LLM returns invalid shape."""
    filtered_utterances = []
    for utterance in transcript.utterances:
        text = utterance.text
        included = len(text.strip()) > 0
        filtered_utterances.append({
            "speaker": utterance.speaker,
            "utterance": text,
            "included": included,
            "maps_to": _map_utterance_to_section(utterance.speaker, text) if included else None,
            "reason": "Fallback filter: retained utterance for downstream clinical extraction",
            "speaker_uncertain": utterance.confidence < 0.8,
        })

    lab_value_verification = []
    if isinstance(test_report_values, dict):
        for lab_name, lab_data in test_report_values.items():
            if not isinstance(lab_data, dict):
                continue
            lab_value_verification.append({
                "lab_value": f"{lab_name}: {lab_data.get('value', '')}",
                "value": f"{lab_name}: {lab_data.get('value', '')}",
                "source": "ocr_only",
                "verified": bool(lab_data.get("verified", True)),
                "flag": lab_data.get("flag"),
            })

    return {
        "filtered_utterances": filtered_utterances,
        "lab_value_verification": lab_value_verification,
        "utterances_excluded_count": 0,
        "speaker_uncertain_count": sum(1 for u in filtered_utterances if u["speaker_uncertain"]),
    }


def _keyword_rescue_filter_payload(transcript, test_report_values: dict, existing_payload: dict) -> dict:
    """Recover clinically relevant utterances without blindly including everything."""
    clinical_keywords = [
        "pain",
        "mg",
        "dosage",
        "diagnosis",
        "prescribed",
        "symptom",
        "blood",
        "pressure",
        "glucose",
        "fever",
        "breathing",
        "chest",
        "heart",
        "medication",
        "history",
    ]
    existing_by_text = {
        item.get("utterance", ""): item
        for item in existing_payload.get("filtered_utterances", [])
        if isinstance(item, dict)
    }
    rescued = []
    for utterance in transcript.utterances:
        text = utterance.text or ""
        lower = text.lower()
        include = any(keyword in lower for keyword in clinical_keywords)
        previous = existing_by_text.get(text, {})
        rescued.append({
            "speaker": utterance.speaker,
            "utterance": text,
            "included": include,
            "maps_to": _map_utterance_to_section(utterance.speaker, text) if include else None,
            "reason": (
                "Keyword rescue: retained clinically relevant utterance"
                if include else previous.get("reason", "Keyword rescue: no clinical keyword found")
            ),
            "speaker_uncertain": utterance.confidence < 0.8 or utterance.speaker == "uncertain",
        })

    return {
        "filtered_utterances": rescued,
        "lab_value_verification": existing_payload.get("lab_value_verification", []),
        "utterances_excluded_count": sum(1 for item in rescued if not item["included"]),
        "speaker_uncertain_count": sum(1 for item in rescued if item["speaker_uncertain"]),
    }


# SPECIFIC SYSTEM PROMPT - NOT GENERIC
FILTER_SYSTEM_PROMPT = """ROLE:
You are the clinical relevance filter for MedScribe, processing raw diarized 
consultation transcripts before clinical extraction begins. You determine which 
parts of the conversation are clinically relevant and must explain every 
inclusion and exclusion decision.

TASK:

STEP 1 — RELEVANCE FILTERING:
Evaluate every utterance in the transcript.
Mark each as included or excluded.

INCLUDE utterances containing:
- Patient-reported symptoms or complaints
- Duration or frequency of symptoms
- Medication names, dosages, or frequency
- Vital signs or numerical test values
- Family history of medical conditions
- Doctor clinical observations
- Doctor diagnoses or assessments
- Doctor prescriptions or treatment instructions

EXCLUDE utterances containing:
- Greetings or farewells
- Conversational filler phrases
- Scheduling or administrative content
- Repeated statements already captured
- Non-clinical small talk

For every included utterance: state which SOAP section it maps to and why it was included.
For every excluded utterance: state exactly why.

STEP 2 — SPEAKER ATTRIBUTION CHECK:
For each included utterance check Whisper speaker confidence score.
If speaker confidence < 0.80:
- Mark speaker_uncertain: true
- Exclude from clinical extraction
- Flag for physician manual attribution review
- Never assume speaker identity when uncertain

STEP 3 — LAB VALUE CROSS-VERIFICATION:
For every lab value mentioned verbally in transcript:
- Check if same value exists in test_report_values
- If match: verified: true, source: both
- If no match: verified: false, source: transcript_only,
  flag: verbally mentioned but not confirmed by test report — physician to verify

For every lab value from OCR:
- Mark verified: true, source: ocr_only or both

OUTPUT FORMAT (JSON):
{
  "filtered_utterances": [
    {
      "speaker": "Patient",
      "utterance": "exact text",
      "included": true,
      "maps_to": "Subjective",
      "reason": "patient-reported symptom with duration",
      "speaker_uncertain": false
    },
    {
      "speaker": "Doctor",
      "utterance": "Good morning",
      "included": false,
      "maps_to": null,
      "reason": "conversational greeting, no clinical content",
      "speaker_uncertain": false
    }
  ],
  "lab_value_verification": [],
  "utterances_excluded_count": 0,
  "speaker_uncertain_count": 0
}

CONSTRAINTS:
- Never exclude without stating reason
- Never include without mapping to SOAP section
- Speaker uncertain utterances always excluded
- Verbally mentioned lab values without OCR match always flagged — never silently included
- If diarization unavailable: mark all utterances speaker_uncertain and flag entire transcript for physician attribution review
- Speaker values MUST be exactly one of: "Patient", "Doctor", or "uncertain" — never use brackets"""


def clinical_relevance_filter(state: PipelineState) -> PipelineState:
    """
    Node 7: Clinical Relevance Filter (Agent 1).

    Runs after transcription and diarization. Phase 6 keeps the filter selective
    by using keyword rescue before falling back to last-resort include-all.
    """
    logger.info("=" * 80)
    logger.info("NODE 7: Clinical Relevance Filter")
    logger.info("=" * 80)

    transcript = state.get("transcript_diarized")
    if not transcript:
        error_msg = "No transcript available for filtering"
        logger.error(error_msg)
        state["error"] = error_msg
        return state

    logger.info("Input: %d diarized utterances", len(transcript.utterances))

    utterances_text = "\n".join([
        f"[{u.speaker}] (confidence: {u.confidence:.2f}): {u.text}"
        for u in transcript.utterances
    ])
    logger.debug("Formatted transcript:\n%s...", utterances_text[:500])

    test_report_values = state.get("test_report_values", {})
    ocr_result = state.get("ocr_result", {})
    ocr_status = ocr_result.get("status", "unknown") if isinstance(ocr_result, dict) else "unknown"
    ocr_values_text = json.dumps(_plain(test_report_values), indent=2)

    user_prompt = f"""Raw transcript:
{utterances_text}

OCR status: {ocr_status}
OCR test values:
{ocr_values_text}

Please filter this transcript and output the JSON format specified."""

    llm = get_llm_service()
    try:
        logger.info("Calling LLM for clinical relevance filtering...")
        response_text = llm.generate(
            FILTER_SYSTEM_PROMPT,
            user_prompt,
            temperature=0.1,
        )
        filtered_data = _extract_json_from_response(response_text)
        if filtered_data is None:
            raise json.JSONDecodeError(
                "Failed to extract valid JSON from Clinical Relevance Filter response",
                response_text,
                0,
            )
        filtered_data = _normalize_filter_payload(filtered_data)

        if "filtered_utterances" not in filtered_data:
            logger.warning("Filter response missing filtered_utterances; using deterministic fallback")
            filtered_data = _normalize_filter_payload(_fallback_filter_payload(transcript, test_report_values))

        included_count = sum(1 for u in filtered_data["filtered_utterances"] if u["included"])
        excluded_count = filtered_data.get("utterances_excluded_count", 0)

        if included_count < 2:
            diarization_method = state.get("diarization_method", "unknown")
            if diarization_method != "fallback":
                logger.warning(
                    "Filter included fewer than 2 utterances with %s diarization; "
                    "filter may be too strict, applying keyword rescue",
                    diarization_method,
                )
            else:
                logger.warning("Fallback diarization included fewer than 2 utterances; applying keyword rescue")
            rescued_data = _keyword_rescue_filter_payload(transcript, test_report_values, filtered_data)
            rescued_count = sum(1 for u in rescued_data["filtered_utterances"] if u["included"])

            if rescued_count > 0:
                filtered_data = _normalize_filter_payload(rescued_data)
                included_count = rescued_count
                excluded_count = filtered_data["utterances_excluded_count"]
                logger.warning("Keyword rescue retained %d utterances", rescued_count)
            elif diarization_method == "fallback":
                logger.warning("Fallback diarization with no rescued utterances; last-resort include-all enabled")
                fallback_data = _fallback_filter_payload(transcript, test_report_values)
                for utterance in fallback_data["filtered_utterances"]:
                    utterance["reason"] = "Last-resort fallback: diarization unavailable and no clinical keywords rescued"
                fallback_data["utterances_excluded_count"] = 0
                filtered_data = _normalize_filter_payload(fallback_data)
                included_count = len(filtered_data["filtered_utterances"])
                excluded_count = 0
            else:
                logger.warning(
                    "Real diarization method %s produced low clinical inclusion; trusting filtered result",
                    diarization_method,
                )

        state["filtered_transcript"] = FilteredTranscript(**filtered_data)

        logger.info("Filter complete:")
        logger.info("   Total utterances: %d", len(filtered_data["filtered_utterances"]))
        logger.info("   Included: %d", included_count)
        logger.info("   Excluded: %d", excluded_count)

        included_samples = [u for u in filtered_data["filtered_utterances"] if u["included"]][:3]
        if included_samples:
            logger.info("   Sample included utterances:")
            for utterance in included_samples:
                logger.info(
                    "      - [%s] %s... -> %s",
                    utterance["speaker"],
                    utterance["utterance"][:50],
                    utterance["maps_to"],
                )

    except json.JSONDecodeError as e:
        logger.error("Failed to parse filter response as JSON: %s", e)
        state["error"] = f"JSON parse error in Clinical Relevance Filter: {str(e)}"
    except Exception as e:
        logger.error("Error in Clinical Relevance Filter: %s", e)
        import traceback
        logger.error(traceback.format_exc())
        state["error"] = f"Clinical Relevance Filter error: {str(e)}"

    return state

# Made with Bob
