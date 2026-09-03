"""
Clinical Safety Guardrail Node
Checks for patient safety risks using deterministic rules.
"""
import logging
import re
from typing import Any

from backend.pipeline.state import PipelineState

logger = logging.getLogger(__name__)

DANGEROUS_PAIRS = [
    ("warfarin", "aspirin"),
    ("warfarin", "ibuprofen"),
    ("warfarin", "naproxen"),
    ("ssri", "maoi"),
    ("fluoxetine", "maoi"),
    ("sertraline", "maoi"),
    ("metformin", "contrast"),
    ("ace inhibitor", "potassium"),
    ("lisinopril", "potassium"),
    ("ramipril", "potassium"),
    ("nsaid", "anticoagulant"),
    ("ibuprofen", "warfarin"),
    ("digoxin", "amiodarone"),
    ("fluoroquinolone", "corticosteroid"),
    ("ciprofloxacin", "corticosteroid"),
]

RED_FLAG_TERMS = [
    ("myocardial infarction", "urgent"),
    ("heart attack", "urgent"),
    ("acute coronary", "urgent"),
    ("stroke", "urgent"),
    ("tia", "urgent"),
    ("transient ischemic", "urgent"),
    ("sepsis", "urgent"),
    ("septic shock", "urgent"),
    ("respiratory failure", "urgent"),
    ("hypertensive emergency", "urgent"),
    ("hypertensive crisis", "urgent"),
    ("diabetic ketoacidosis", "urgent"),
    ("dka", "urgent"),
    ("pulmonary embolism", "urgent"),
    ("anaphylaxis", "urgent"),
]

DOSAGE_LIMITS = {
    "metformin": 2550,
    "lisinopril": 40,
    "amlodipine": 10,
    "atorvastatin": 80,
    "aspirin": 4000,
    "ibuprofen": 3200,
    "paracetamol": 4000,
    "acetaminophen": 4000,
}


def _get_value(item: Any, key: str, default: Any = "") -> Any:
    """Read values from either dicts or Pydantic-style objects."""
    if item is None:
        return default
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def check_drug_interactions(medications: list) -> list:
    flags = []
    med_texts = [
        str(_get_value(med, "drug", "") or "").lower()
        for med in medications
    ]
    plan_text = " ".join(med_texts)

    for drug_a, drug_b in DANGEROUS_PAIRS:
        if drug_a in plan_text and drug_b in plan_text:
            flags.append({
                "check_type": "drug_interaction",
                "detail": f"Dangerous combination detected: {drug_a} + {drug_b}",
                "urgency": "urgent",
                "terms": [drug_a, drug_b],
            })
    return flags


def check_red_flag_diagnoses(assessment: str) -> list:
    flags = []
    assessment_lower = (assessment or "").lower()

    for term, urgency in RED_FLAG_TERMS:
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, assessment_lower):
            flags.append({
                "check_type": "red_flag_diagnosis",
                "detail": f"Red flag diagnosis detected: {term}",
                "urgency": urgency,
            })
    return flags


def check_dosage_risks(medications: list) -> list:
    flags = []

    for med in medications:
        drug = str(_get_value(med, "drug", "") or "").lower()
        dosage_str = str(_get_value(med, "dosage", "") or "")

        for drug_name, max_dose in DOSAGE_LIMITS.items():
            if drug_name in drug:
                numbers = re.findall(r"\d+\.?\d*", dosage_str)
                if numbers:
                    dose = float(numbers[0])
                    if dose > max_dose:
                        flags.append({
                            "check_type": "dosage_risk",
                            "detail": f"{drug} dose {dose}mg exceeds maximum {max_dose}mg",
                            "urgency": "review",
                            "terms": [drug_name],
                        })
    return flags


def check_allergy_conflicts(plan_text: str, allergies: str) -> list:
    flags = []
    allergy_terms = [
        term.strip().lower()
        for term in re.split(r"[,;\n]", allergies or "")
        if term.strip()
    ]
    plan_lower = (plan_text or "").lower()

    for term in allergy_terms:
        pattern = rf"\b{re.escape(term)}\b"
        if re.search(pattern, plan_lower):
            flags.append({
                "check_type": "allergy_conflict",
                "detail": f"Plan mentions {term}, which is listed in patient allergies",
                "urgency": "urgent",
                "terms": [term],
            })

    return flags


def run_safety_check(state: dict) -> dict:
    soap_note = state.get("soap_note")
    extracted = state.get("extracted_entities")

    if not soap_note or not extracted:
        return {"safety_pass": True, "safety_flags": []}

    all_flags = []

    medications = _get_value(extracted, "medications", []) or []
    patient_context = state.get("patient_context", {}) or {}
    current_meds = str(patient_context.get("current_meds", "") or "").strip()
    allergies = str(patient_context.get("allergies", "") or "").strip()
    if current_meds:
        medications = list(medications) + [{
            "drug": current_meds,
            "dosage": "",
            "frequency": "",
        }]

    assessment_text = ""
    assessment = _get_value(soap_note, "assessment", None)
    if assessment:
        assessment_text = str(_get_value(assessment, "content", "") or "")

    plan_text = ""
    plan = _get_value(soap_note, "plan", None)
    if plan:
        plan_text = str(_get_value(plan, "content", "") or "")

    all_flags.extend(check_drug_interactions(medications))
    all_flags.extend(check_red_flag_diagnoses(assessment_text))
    all_flags.extend(check_allergy_conflicts(plan_text, allergies))

    plan_med_check = check_drug_interactions(list(medications) + [{"drug": plan_text}])
    for flag in plan_med_check:
        if flag not in all_flags:
            all_flags.append(flag)

    all_flags.extend(check_dosage_risks(medications))

    return {
        "safety_pass": len(all_flags) == 0,
        "safety_flags": all_flags,
    }


def safety_guardrail(state: PipelineState) -> PipelineState:
    """
    Safety Guardrail Node: Check for patient safety risks.

    Input: soap_note, extracted_entities
    Output: safety_result
    """
    logger.info("Node 14: Safety Guardrail - Checking for safety risks...")

    try:
        safety_result = run_safety_check(state)
        state["safety_result"] = safety_result

        logger.info(
            "Safety check complete: pass=%s, flags=%s",
            safety_result["safety_pass"],
            len(safety_result["safety_flags"]),
        )

        urgent_flags = [
            flag
            for flag in safety_result["safety_flags"]
            if flag.get("urgency") == "urgent"
        ]
        if urgent_flags:
            logger.warning("URGENT SAFETY FLAGS: %s", len(urgent_flags))
            for flag in urgent_flags:
                logger.warning(
                    "  - %s: %s",
                    flag.get("check_type"),
                    flag.get("detail"),
                )

    except Exception as e:
        logger.error(f"Safety guardrail failed: {e}")
        state["safety_result"] = {
            "safety_pass": False,
            "safety_flags": [{
                "check_type": "system_error",
                "detail": f"Safety validation error: {str(e)}",
                "urgency": "review",
            }],
        }
        state["error"] = f"Safety error: {str(e)}"

    return state


# Made with Bob
