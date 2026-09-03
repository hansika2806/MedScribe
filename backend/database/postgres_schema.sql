-- MedScribe PostgreSQL Schema
-- Production-ready schema with proper constraints, indexes, and audit support

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Consultations table
CREATE TABLE IF NOT EXISTS consultations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL CHECK (status IN ('pending', 'processing', 'completed', 'failed')),
    review_type VARCHAR(50) CHECK (review_type IN ('urgent_safety', 'low_confidence', 'standard_approval')),
    diarization_method VARCHAR(50),
    processing_time_seconds DECIMAL(10, 2),
    error_message TEXT,
    patient_context JSONB,
    physician_username VARCHAR(100) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- SOAP notes table
CREATE TABLE IF NOT EXISTS soap_notes (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    subjective_content TEXT,
    subjective_confidence DECIMAL(5, 4) CHECK (subjective_confidence BETWEEN 0 AND 1),
    objective_content TEXT,
    objective_confidence DECIMAL(5, 4) CHECK (objective_confidence BETWEEN 0 AND 1),
    assessment_content TEXT,
    assessment_confidence DECIMAL(5, 4) CHECK (assessment_confidence BETWEEN 0 AND 1),
    plan_content TEXT,
    plan_confidence DECIMAL(5, 4) CHECK (plan_confidence BETWEEN 0 AND 1),
    overall_confidence DECIMAL(5, 4) CHECK (overall_confidence BETWEEN 0 AND 1),
    approved BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id)
);

-- Diagnoses table
CREATE TABLE IF NOT EXISTS diagnoses (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    diagnosis_text TEXT NOT NULL,
    icd10_code VARCHAR(10),
    icd10_description TEXT,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Provenance records table
CREATE TABLE IF NOT EXISTS provenance_records (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    soap_section VARCHAR(20) CHECK (soap_section IN ('subjective', 'objective', 'assessment', 'plan')),
    claim TEXT NOT NULL,
    source VARCHAR(50),
    speaker VARCHAR(50),
    utterance TEXT,
    verified BOOLEAN DEFAULT FALSE,
    confidence DECIMAL(5, 4) CHECK (confidence BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Retrieved guidelines table
CREATE TABLE IF NOT EXISTS retrieved_guidelines (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    source VARCHAR(100),
    year VARCHAR(10),
    section TEXT,
    content TEXT NOT NULL,
    relevance_score DECIMAL(5, 4),
    population_match TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- QA results table
CREATE TABLE IF NOT EXISTS qa_results (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    overall_confidence DECIMAL(5, 4) CHECK (overall_confidence BETWEEN 0 AND 1),
    subjective_score DECIMAL(5, 4),
    objective_score DECIMAL(5, 4),
    assessment_score DECIMAL(5, 4),
    plan_score DECIMAL(5, 4),
    flags JSONB,
    passed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id)
);

-- Safety results table
CREATE TABLE IF NOT EXISTS safety_results (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    safety_pass BOOLEAN DEFAULT TRUE,
    safety_flags JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id)
);

-- Lab values table
CREATE TABLE IF NOT EXISTS lab_values (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    lab_name VARCHAR(100) NOT NULL,
    value VARCHAR(50),
    unit VARCHAR(20),
    reference_range TEXT,
    display_name VARCHAR(200),
    interpretation VARCHAR(50),
    source VARCHAR(50),
    verified BOOLEAN DEFAULT FALSE,
    flag VARCHAR(20) CHECK (flag IN ('normal', 'high', 'low', 'critical')),
    entered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Approvals table
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    physician_username VARCHAR(100) NOT NULL,
    physician_name VARCHAR(200),
    approved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(session_id)
);

-- Audit log table (for compliance)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES consultations(id) ON DELETE SET NULL,
    user_id VARCHAR(100),
    action VARCHAR(100) NOT NULL,
    table_name VARCHAR(100),
    record_id VARCHAR(100),
    old_values JSONB,
    new_values JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Performance metrics table
CREATE TABLE IF NOT EXISTS performance_metrics (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES consultations(id) ON DELETE SET NULL,
    node_name VARCHAR(100) NOT NULL,
    status VARCHAR(20) CHECK (status IN ('success', 'failure')),
    duration_seconds DECIMAL(10, 4),
    input_size INTEGER,
    output_size INTEGER,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_consultations_physician ON consultations(physician_username);
CREATE INDEX idx_consultations_status ON consultations(status);
CREATE INDEX idx_consultations_created ON consultations(created_at DESC);
CREATE INDEX idx_consultations_physician_created ON consultations(physician_username, created_at DESC);

CREATE INDEX idx_soap_notes_session ON soap_notes(session_id);
CREATE INDEX idx_soap_notes_approved ON soap_notes(approved);
CREATE INDEX idx_soap_notes_confidence ON soap_notes(overall_confidence);

CREATE INDEX idx_diagnoses_session ON diagnoses(session_id);
CREATE INDEX idx_diagnoses_icd10 ON diagnoses(icd10_code);

CREATE INDEX idx_provenance_session ON provenance_records(session_id);
CREATE INDEX idx_provenance_section ON provenance_records(soap_section);

CREATE INDEX idx_guidelines_session ON retrieved_guidelines(session_id);
CREATE INDEX idx_guidelines_source ON retrieved_guidelines(source);

CREATE INDEX idx_qa_session ON qa_results(session_id);
CREATE INDEX idx_qa_passed ON qa_results(passed);

CREATE INDEX idx_safety_session ON safety_results(session_id);
CREATE INDEX idx_safety_pass ON safety_results(safety_pass);

CREATE INDEX idx_lab_values_session ON lab_values(session_id);
CREATE INDEX idx_lab_values_name ON lab_values(lab_name);

CREATE INDEX idx_approvals_session ON approvals(session_id);
CREATE INDEX idx_approvals_physician ON approvals(physician_username);

CREATE INDEX idx_audit_log_session ON audit_log(session_id);
CREATE INDEX idx_audit_log_user ON audit_log(user_id);
CREATE INDEX idx_audit_log_action ON audit_log(action);
CREATE INDEX idx_audit_log_created ON audit_log(created_at DESC);

CREATE INDEX idx_performance_session ON performance_metrics(session_id);
CREATE INDEX idx_performance_node ON performance_metrics(node_name);
CREATE INDEX idx_performance_created ON performance_metrics(created_at DESC);

-- Trigger for updated_at timestamps
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_consultations_updated_at BEFORE UPDATE ON consultations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_soap_notes_updated_at BEFORE UPDATE ON soap_notes
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Audit trigger function
CREATE OR REPLACE FUNCTION audit_trigger_function()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'DELETE') THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values)
        VALUES (TG_TABLE_NAME, OLD.id::TEXT, 'DELETE', row_to_json(OLD));
        RETURN OLD;
    ELSIF (TG_OP = 'UPDATE') THEN
        INSERT INTO audit_log (table_name, record_id, action, old_values, new_values)
        VALUES (TG_TABLE_NAME, NEW.id::TEXT, 'UPDATE', row_to_json(OLD), row_to_json(NEW));
        RETURN NEW;
    ELSIF (TG_OP = 'INSERT') THEN
        INSERT INTO audit_log (table_name, record_id, action, new_values)
        VALUES (TG_TABLE_NAME, NEW.id::TEXT, 'INSERT', row_to_json(NEW));
        RETURN NEW;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Apply audit triggers to critical tables
CREATE TRIGGER audit_consultations AFTER INSERT OR UPDATE OR DELETE ON consultations
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_soap_notes AFTER INSERT OR UPDATE OR DELETE ON soap_notes
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

CREATE TRIGGER audit_approvals AFTER INSERT OR UPDATE OR DELETE ON approvals
    FOR EACH ROW EXECUTE FUNCTION audit_trigger_function();

-- Views for common queries
CREATE OR REPLACE VIEW consultation_summary AS
SELECT 
    c.id,
    c.physician_username,
    c.status,
    c.review_type,
    c.created_at,
    c.completed_at,
    c.processing_time_seconds,
    sn.overall_confidence,
    sn.approved,
    sn.approved_at,
    COUNT(DISTINCT d.id) as diagnosis_count,
    COUNT(DISTINCT lv.id) as lab_value_count,
    qa.passed as qa_passed,
    sr.safety_pass
FROM consultations c
LEFT JOIN soap_notes sn ON c.id = sn.session_id
LEFT JOIN diagnoses d ON c.id = d.session_id
LEFT JOIN lab_values lv ON c.id = lv.session_id
LEFT JOIN qa_results qa ON c.id = qa.session_id
LEFT JOIN safety_results sr ON c.id = sr.session_id
GROUP BY c.id, sn.overall_confidence, sn.approved, sn.approved_at, qa.passed, sr.safety_pass;

-- Made with Bob
