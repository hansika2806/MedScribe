from langgraph.graph import StateGraph, END
from backend.pipeline.state import PipelineState
from backend.pipeline.nodes.filter import clinical_relevance_filter
from backend.pipeline.nodes.extractor import clinical_extractor
from backend.pipeline.nodes.soap import soap_generator
from backend.pipeline.nodes.rag import rag_node
from backend.pipeline.nodes.icd10_node import icd10_node
from backend.pipeline.nodes.qa_guardrail import qa_guardrail
from backend.pipeline.nodes.safety_guardrail import safety_guardrail
from backend.tools.whisper import get_transcriber
from backend.tools.diarization import diarize
import logging

logger = logging.getLogger(__name__)


def transcribe_and_diarize_node(state: PipelineState) -> PipelineState:
    """
    Node 2: Transcribe audio with faster-whisper and apply diarization
    
    Tries real diarization (Speechbrain) first, falls back to alternating
    """
    logger.info("Node 2: Transcribing audio with faster-whisper...")
    try:
        transcriber = get_transcriber()
        state["transcript_raw"] = transcriber.transcribe(state["audio_path"])
        logger.info(f"Transcription complete: {len(state['transcript_raw'])} characters")
        
        # Apply diarization (tries Speechbrain, falls back to alternating)
        logger.info("Applying diarization...")
        diarized = diarize(
            state["audio_path"],
            state["transcript_raw"]
        )
        state["transcript_diarized"] = diarized
        
        # Track which method was used
        if diarized.source == "whisper" and diarized.diarization_available:
            state["diarization_method"] = "speechbrain"
        else:
            state["diarization_method"] = "fallback"
        
        logger.info(f"Diarization complete: {len(diarized.utterances)} utterances (method: {state['diarization_method']})")
        
    except Exception as e:
        logger.error(f"Transcription/Diarization failed: {e}")
        state["error"] = f"Transcription/Diarization error: {str(e)}"
    return state


def urgent_handoff_node(state: PipelineState) -> PipelineState:
    """
    Node 15: Urgent handoff for safety flags
    """
    logger.warning("⚠️ URGENT HANDOFF - Safety flags detected")
    state["requires_physician_review"] = True
    state["review_type"] = "urgent_safety"
    state["review_message"] = (
        "URGENT: Safety flags detected. "
        "Immediate physician review required."
    )
    return state


def review_handoff_node(state: PipelineState) -> PipelineState:
    """
    Node 16: Review handoff for low confidence
    """
    logger.info("📋 REVIEW HANDOFF - Low confidence or QA flags")
    state["requires_physician_review"] = True
    state["review_type"] = "low_confidence"
    state["review_message"] = (
        "SOAP note below quality threshold. "
        "Physician review required before saving."
    )
    return state


def output_node(state: PipelineState) -> PipelineState:
    """
    Output node: High confidence, passed all checks
    """
    logger.info("✅ OUTPUT - SOAP note passed automated QA")
    state["requires_physician_review"] = True
    state["review_type"] = "standard_approval"
    state["review_message"] = (
        "SOAP note passed automated QA. "
        "Please review and approve to save."
    )
    return state


def route_after_safety(state: PipelineState) -> str:
    """
    Route after safety guardrail
    
    Returns:
        "urgent_handoff" if safety flags exist
        "confidence_router" otherwise
    """
    safety_result = state.get("safety_result", {})
    if not safety_result.get("safety_pass", True):
        logger.warning("Routing to urgent_handoff due to safety flags")
        return "urgent_handoff"
    return "confidence_router"


def route_after_confidence(state: PipelineState) -> str:
    """
    Route after confidence check
    
    Returns:
        "output" if high confidence and QA passed
        "review_handoff" otherwise
    """
    qa_result = state.get("qa_result", {})
    overall_confidence = qa_result.get("overall_confidence", 0.0)
    qa_pass = qa_result.get("pass", False)
    
    if overall_confidence >= 0.85 and qa_pass:
        logger.info("Routing to output - high confidence")
        return "output"
    else:
        logger.info("Routing to review_handoff - low confidence or QA flags")
        return "review_handoff"


def confidence_router_node(state: PipelineState) -> PipelineState:
    """
    Dummy node for confidence routing
    Just passes state through - actual routing done by conditional edge
    """
    return state


def build_pipeline():
    """
    Build Phase 2 LangGraph pipeline
    
    Flow:
    1. Node 2: Transcribe & Diarize (faster-whisper + Speechbrain/fallback)
    2. Node 7: Filter (Clinical Relevance Filter)
    3. Node 8: Extract (Clinical Extractor)
    4. Node 10: RAG (Retrieve clinical guidelines)
    5. Node 11: Generate SOAP (SOAP Generator with guidelines)
    6. Node 12: ICD-10 (Look up diagnosis codes)
    7. Node 13: QA Guardrail (Quality check)
    8. Node 14: Safety Guardrail (Safety check)
    9. Safety Router → [urgent_handoff OR confidence_router]
    10. Confidence Router → [output OR review_handoff]
    11. All three → END
    """
    logger.info("Building Phase 2 pipeline...")
    
    workflow = StateGraph(PipelineState)
    
    # Add nodes in execution order
    workflow.add_node("transcribe", transcribe_and_diarize_node)
    workflow.add_node("filter", clinical_relevance_filter)
    workflow.add_node("extract", clinical_extractor)
    workflow.add_node("rag", rag_node)
    workflow.add_node("soap", soap_generator)
    workflow.add_node("icd10", icd10_node)
    workflow.add_node("qa_guardrail", qa_guardrail)
    workflow.add_node("safety_guardrail", safety_guardrail)
    workflow.add_node("confidence_router", confidence_router_node)
    workflow.add_node("urgent_handoff", urgent_handoff_node)
    workflow.add_node("review_handoff", review_handoff_node)
    workflow.add_node("output", output_node)
    
    # Define linear edges
    workflow.set_entry_point("transcribe")
    workflow.add_edge("transcribe", "filter")
    workflow.add_edge("filter", "extract")
    workflow.add_edge("extract", "rag")
    workflow.add_edge("rag", "soap")
    workflow.add_edge("soap", "icd10")
    workflow.add_edge("icd10", "qa_guardrail")
    workflow.add_edge("qa_guardrail", "safety_guardrail")
    
    # Conditional routing after safety
    workflow.add_conditional_edges(
        "safety_guardrail",
        route_after_safety,
        {
            "urgent_handoff": "urgent_handoff",
            "confidence_router": "confidence_router"
        }
    )
    
    # Conditional routing after confidence
    workflow.add_conditional_edges(
        "confidence_router",
        route_after_confidence,
        {
            "output": "output",
            "review_handoff": "review_handoff"
        }
    )
    
    # All terminal nodes go to END
    workflow.add_edge("urgent_handoff", END)
    workflow.add_edge("review_handoff", END)
    workflow.add_edge("output", END)
    
    logger.info("Pipeline built successfully")
    logger.info("Execution order: transcribe → filter → extract → rag → soap → icd10 → qa → safety → routing")
    
    return workflow.compile()


# Singleton instance
_pipeline = None


def get_pipeline():
    """Get or create pipeline instance"""
    global _pipeline
    if _pipeline is None:
        _pipeline = build_pipeline()
        logger.info("Pipeline compiled and ready")
    return _pipeline


# Made with Bob
