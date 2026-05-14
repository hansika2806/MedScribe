from backend.pipeline.state import PipelineState
from backend.services.llm import get_llm_service
from backend.models.schemas import FilteredTranscript
import json
import logging

logger = logging.getLogger(__name__)

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
- If diarization unavailable: mark all utterances speaker_uncertain and flag entire transcript for physician attribution review"""


def clinical_relevance_filter(state: PipelineState) -> PipelineState:
    """
    Node 7: Clinical Relevance Filter (Agent 1)
    
    Runs AFTER transcription and diarization complete.
    Determines which utterances are clinically relevant.
    """
    logger.info("=" * 80)
    logger.info("NODE 7: Clinical Relevance Filter")
    logger.info("=" * 80)
    
    transcript = state.get("transcript_diarized")
    if not transcript:
        error_msg = "No transcript available for filtering"
        logger.error(f"❌ {error_msg}")
        state["error"] = error_msg
        return state
    
    logger.info(f"📝 Input: {len(transcript.utterances)} diarized utterances")
    
    # Format utterances for LLM
    utterances_text = "\n".join([
        f"[{u.speaker}] (confidence: {u.confidence:.2f}): {u.text}"
        for u in transcript.utterances
    ])
    
    logger.debug(f"Formatted transcript:\n{utterances_text[:500]}...")
    
    user_prompt = f"""Raw transcript:
{utterances_text}

OCR test values: Not available in Phase 1 (will be added in Phase 2)

Please filter this transcript and output the JSON format specified."""
    
    # Call LLM
    llm = get_llm_service()
    try:
        logger.info("🤖 Calling LLM for clinical relevance filtering...")
        filtered_data = llm.generate_json(FILTER_SYSTEM_PROMPT, user_prompt)
        
        # Validate required fields
        if "filtered_utterances" not in filtered_data:
            raise ValueError("Response missing 'filtered_utterances' field")
        
        included_count = sum(1 for u in filtered_data['filtered_utterances'] if u['included'])
        excluded_count = filtered_data.get('utterances_excluded_count', 0)
        
        # FALLBACK: If less than 2 utterances included, bypass filter and include all
        if included_count < 2:
            logger.warning("⚠️  Filter excluded too many utterances (< 2 included)")
            logger.warning("⚠️  Bypassing filter - passing ALL utterances to Clinical Extractor")
            
            # Mark all utterances as included
            for utterance in filtered_data['filtered_utterances']:
                utterance['included'] = True
                if not utterance.get('maps_to'):
                    utterance['maps_to'] = 'Subjective'  # Default mapping
                utterance['reason'] = 'Fallback: filter bypassed due to low inclusion rate'
            
            included_count = len(filtered_data['filtered_utterances'])
            excluded_count = 0
            filtered_data['utterances_excluded_count'] = 0
        
        # Create FilteredTranscript object
        state["filtered_transcript"] = FilteredTranscript(**filtered_data)
        
        logger.info(f"✅ Filter complete:")
        logger.info(f"   Total utterances: {len(filtered_data['filtered_utterances'])}")
        logger.info(f"   Included: {included_count}")
        logger.info(f"   Excluded: {excluded_count}")
        
        # Log sample of included utterances
        included_samples = [u for u in filtered_data['filtered_utterances'] if u['included']][:3]
        if included_samples:
            logger.info(f"   Sample included utterances:")
            for u in included_samples:
                logger.info(f"      - [{u['speaker']}] {u['utterance'][:50]}... → {u['maps_to']}")
        
    except json.JSONDecodeError as e:
        logger.error(f"❌ Failed to parse filter response as JSON: {e}")
        state["error"] = f"JSON parse error in Clinical Relevance Filter: {str(e)}"
    except Exception as e:
        logger.error(f"❌ Error in Clinical Relevance Filter: {e}")
        import traceback
        logger.error(traceback.format_exc())
        state["error"] = f"Clinical Relevance Filter error: {str(e)}"
    
    return state

# Made with Bob
