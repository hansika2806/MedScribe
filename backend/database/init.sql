-- MedScribe PostgreSQL Database Initialization Script
-- This script creates the database schema with proper indexes and constraints

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create consultations table
CREATE TABLE IF NOT EXISTS consultations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    status VARCHAR(50) NOT NULL,
    review_type VARCHAR(50),
    diarization_method VARCHAR(50),
    processing_time_seconds REAL,
    error_message TEXT,
    patient_context JSONB,
    physician_username VARCHAR(100) NOT NULL DEFAULT 'unknown',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Indexes for common queries
    CONSTRAINT consultations_status_check CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'approved'))
);

CREATE INDEX idx_consultations_physician ON consultations(physician_username);
CREATE INDEX idx_consultations_status ON consultations(status);
CREATE INDEX idx_consultations_created_at ON consultations(created_at DESC);

-- Create SOAP notes table
CREATE TABLE IF NOT EXISTS soap_notes (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    subjective_content TEXT,
    subjective_confidence REAL,
    objective_content TEXT,
    objective_confidence REAL,
    assessment_content TEXT,
    assessment_confidence REAL,
    plan_content TEXT,
    plan_confidence REAL,
    overall_confidence REAL,
    approved BOOLEAN DEFAULT FALSE,
    approved_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT soap_notes_confidence_check CHECK (
        overall_confidence >= 0 AND overall_confidence <= 1
    )
);

CREATE INDEX idx_soap_notes_session ON soap_notes(session_id);
CREATE INDEX idx_soap_notes_approved ON soap_notes(approved);

-- Create diagnoses table
CREATE TABLE IF NOT EXISTS diagnoses (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    diagnosis_text TEXT NOT NULL,
    icd10_code VARCHAR(20),
    icd10_description TEXT,
    status VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_diagnoses_session ON diagnoses(session_id);
CREATE INDEX idx_diagnoses_icd10 ON diagnoses(icd10_code);

-- Create provenance records table
CREATE TABLE IF NOT EXISTS provenance_records (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    soap_section VARCHAR(50),
    claim TEXT NOT NULL,
    source VARCHAR(100),
    speaker VARCHAR(50),
    utterance TEXT,
    verified BOOLEAN DEFAULT FALSE,
    confidence REAL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_provenance_session ON provenance_records(session_id);
CREATE INDEX idx_provenance_section ON provenance_records(soap_section);

-- Create retrieved guidelines table
CREATE TABLE IF NOT EXISTS retrieved_guidelines (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    source VARCHAR(200) NOT NULL,
    year VARCHAR(10),
    section TEXT,
    content TEXT NOT NULL,
    relevance_score REAL,
    population_match VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_guidelines_session ON retrieved_guidelines(session_id);
CREATE INDEX idx_guidelines_source ON retrieved_guidelines(source);

-- Create QA results table
CREATE TABLE IF NOT EXISTS qa_results (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    overall_confidence REAL,
    subjective_score REAL,
    objective_score REAL,
    assessment_score REAL,
    plan_score REAL,
    flags JSONB,
    passed BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_qa_session ON qa_results(session_id);
CREATE INDEX idx_qa_passed ON qa_results(passed);

-- Create safety results table
CREATE TABLE IF NOT EXISTS safety_results (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    safety_pass BOOLEAN DEFAULT TRUE,
    safety_flags JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_safety_session ON safety_results(session_id);
CREATE INDEX idx_safety_pass ON safety_results(safety_pass);

-- Create lab values table
CREATE TABLE IF NOT EXISTS lab_values (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    lab_name VARCHAR(200) NOT NULL,
    value VARCHAR(100),
    unit VARCHAR(50),
    reference_range TEXT,
    display_name VARCHAR(200),
    interpretation VARCHAR(50),
    source VARCHAR(100),
    verified BOOLEAN DEFAULT FALSE,
    flag VARCHAR(50),
    entered_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_lab_values_session ON lab_values(session_id);
CREATE INDEX idx_lab_values_name ON lab_values(lab_name);

-- Create approvals table
CREATE TABLE IF NOT EXISTS approvals (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    physician_username VARCHAR(100) NOT NULL,
    physician_name VARCHAR(200),
    approved_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure only one approval per session
    CONSTRAINT unique_session_approval UNIQUE (session_id)
);

CREATE INDEX idx_approvals_session ON approvals(session_id);
CREATE INDEX idx_approvals_physician ON approvals(physician_username);

-- Create audit log table for compliance (Phase 12)
CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    session_id UUID REFERENCES consultations(id) ON DELETE SET NULL,
    physician_username VARCHAR(100) NOT NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_session ON audit_log(session_id);
CREATE INDEX idx_audit_physician ON audit_log(physician_username);
CREATE INDEX idx_audit_action ON audit_log(action);
CREATE INDEX idx_audit_created_at ON audit_log(created_at DESC);

-- Create encrypted data table for PHI encryption at rest
CREATE TABLE IF NOT EXISTS encrypted_data (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES consultations(id) ON DELETE CASCADE,
    data_type VARCHAR(50) NOT NULL,
    encrypted_content BYTEA NOT NULL,
    encryption_version VARCHAR(20) DEFAULT 'v1',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT unique_session_data_type UNIQUE (session_id, data_type)
);

CREATE INDEX idx_encrypted_session ON encrypted_data(session_id);

-- Create function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Grant permissions to medscribe_user
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO medscribe_user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO medscribe_user;

-- Insert initial data or migrations can go here
COMMENT ON TABLE consultations IS 'Main consultation records';
COMMENT ON TABLE soap_notes IS 'Generated SOAP notes for consultations';
COMMENT ON TABLE audit_log IS 'Audit trail for compliance and security';
COMMENT ON TABLE encrypted_data IS 'Encrypted PHI data at rest';

-- Made with Bob
