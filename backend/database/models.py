"""SQLite table definitions for MedScribe Phase 3."""

SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS consultations (
        id TEXT PRIMARY KEY,
        status TEXT,
        review_type TEXT,
        diarization_method TEXT,
        processing_time_seconds REAL,
        error_message TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS soap_notes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        subjective_content TEXT,
        subjective_confidence REAL,
        objective_content TEXT,
        objective_confidence REAL,
        assessment_content TEXT,
        assessment_confidence REAL,
        plan_content TEXT,
        plan_confidence REAL,
        overall_confidence REAL,
        approved INTEGER DEFAULT 0,
        approved_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS diagnoses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        diagnosis_text TEXT,
        icd10_code TEXT,
        icd10_description TEXT,
        status TEXT,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS provenance_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        soap_section TEXT,
        claim TEXT,
        source TEXT,
        speaker TEXT,
        utterance TEXT,
        verified INTEGER,
        confidence REAL,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS retrieved_guidelines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        source TEXT,
        year TEXT,
        section TEXT,
        content TEXT,
        relevance_score REAL,
        population_match TEXT,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS qa_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        overall_confidence REAL,
        subjective_score REAL,
        objective_score REAL,
        assessment_score REAL,
        plan_score REAL,
        flags TEXT,
        passed INTEGER,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS safety_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        safety_pass INTEGER,
        safety_flags TEXT,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lab_values (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        lab_name TEXT,
        value TEXT,
        unit TEXT,
        source TEXT,
        verified INTEGER,
        flag TEXT,
        entered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(session_id) REFERENCES consultations(id)
    )
    """,
]

