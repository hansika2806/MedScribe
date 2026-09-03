"""
SQLite to PostgreSQL Migration Script
Migrates all data from SQLite to PostgreSQL while preserving relationships
"""

import sqlite3
import psycopg2
from psycopg2.extras import execute_values
import logging
from typing import Dict, List, Tuple
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseMigrator:
    """Handles migration from SQLite to PostgreSQL"""
    
    def __init__(self, sqlite_path: str, postgres_conn_string: str):
        self.sqlite_path = sqlite_path
        self.postgres_conn_string = postgres_conn_string
        self.id_mapping: Dict[str, Dict[str, str]] = {}
        
    def connect_sqlite(self) -> sqlite3.Connection:
        """Connect to SQLite database"""
        return sqlite3.connect(self.sqlite_path)
    
    def connect_postgres(self) -> psycopg2.extensions.connection:
        """Connect to PostgreSQL database"""
        return psycopg2.connect(self.postgres_conn_string)
    
    def migrate_consultations(self, sqlite_conn, postgres_conn) -> int:
        """Migrate consultations table"""
        logger.info("Migrating consultations...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        # Fetch all consultations from SQLite
        sqlite_cur.execute("""
            SELECT id, status, review_type, diarization_method, 
                   processing_time_seconds, error_message, physician_username,
                   created_at, completed_at
            FROM consultations
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No consultations to migrate")
            return 0
        
        # Insert into PostgreSQL with UUID generation
        for row in rows:
            old_id = row[0]
            postgres_cur.execute("""
                INSERT INTO consultations 
                (status, review_type, diarization_method, processing_time_seconds,
                 error_message, physician_username, created_at, completed_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, row[1:])
            
            new_id = postgres_cur.fetchone()[0]
            
            # Store mapping for foreign key updates
            if 'consultations' not in self.id_mapping:
                self.id_mapping['consultations'] = {}
            self.id_mapping['consultations'][old_id] = str(new_id)
        
        postgres_conn.commit()
        logger.info(f"Migrated {len(rows)} consultations")
        return len(rows)
    
    def migrate_soap_notes(self, sqlite_conn, postgres_conn) -> int:
        """Migrate SOAP notes table"""
        logger.info("Migrating SOAP notes...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, subjective_content, subjective_confidence,
                   objective_content, objective_confidence, assessment_content,
                   assessment_confidence, plan_content, plan_confidence,
                   overall_confidence, approved, approved_at, created_at
            FROM soap_notes
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No SOAP notes to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                logger.warning(f"Skipping SOAP note for unknown session: {old_session_id}")
                continue
            
            postgres_cur.execute("""
                INSERT INTO soap_notes
                (session_id, subjective_content, subjective_confidence,
                 objective_content, objective_confidence, assessment_content,
                 assessment_confidence, plan_content, plan_confidence,
                 overall_confidence, approved, approved_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} SOAP notes")
        return migrated
    
    def migrate_diagnoses(self, sqlite_conn, postgres_conn) -> int:
        """Migrate diagnoses table"""
        logger.info("Migrating diagnoses...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, diagnosis_text, icd10_code, icd10_description, status
            FROM diagnoses
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No diagnoses to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                logger.warning(f"Skipping diagnosis for unknown session: {old_session_id}")
                continue
            
            postgres_cur.execute("""
                INSERT INTO diagnoses
                (session_id, diagnosis_text, icd10_code, icd10_description, status)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} diagnoses")
        return migrated
    
    def migrate_provenance_records(self, sqlite_conn, postgres_conn) -> int:
        """Migrate provenance records table"""
        logger.info("Migrating provenance records...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, soap_section, claim, source, speaker,
                   utterance, verified, confidence
            FROM provenance_records
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No provenance records to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO provenance_records
                (session_id, soap_section, claim, source, speaker,
                 utterance, verified, confidence)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} provenance records")
        return migrated
    
    def migrate_retrieved_guidelines(self, sqlite_conn, postgres_conn) -> int:
        """Migrate retrieved guidelines table"""
        logger.info("Migrating retrieved guidelines...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, source, year, section, content,
                   relevance_score, population_match
            FROM retrieved_guidelines
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No guidelines to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO retrieved_guidelines
                (session_id, source, year, section, content,
                 relevance_score, population_match)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} guidelines")
        return migrated
    
    def migrate_qa_results(self, sqlite_conn, postgres_conn) -> int:
        """Migrate QA results table"""
        logger.info("Migrating QA results...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, overall_confidence, subjective_score,
                   objective_score, assessment_score, plan_score, flags, passed
            FROM qa_results
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No QA results to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO qa_results
                (session_id, overall_confidence, subjective_score,
                 objective_score, assessment_score, plan_score, flags, passed)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} QA results")
        return migrated
    
    def migrate_safety_results(self, sqlite_conn, postgres_conn) -> int:
        """Migrate safety results table"""
        logger.info("Migrating safety results...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, safety_pass, safety_flags
            FROM safety_results
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No safety results to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO safety_results
                (session_id, safety_pass, safety_flags)
                VALUES (%s, %s, %s::jsonb)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} safety results")
        return migrated
    
    def migrate_lab_values(self, sqlite_conn, postgres_conn) -> int:
        """Migrate lab values table"""
        logger.info("Migrating lab values...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, lab_name, value, unit, reference_range,
                   display_name, interpretation, source, verified, flag, entered_at
            FROM lab_values
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No lab values to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO lab_values
                (session_id, lab_name, value, unit, reference_range,
                 display_name, interpretation, source, verified, flag, entered_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} lab values")
        return migrated
    
    def migrate_approvals(self, sqlite_conn, postgres_conn) -> int:
        """Migrate approvals table"""
        logger.info("Migrating approvals...")
        
        sqlite_cur = sqlite_conn.cursor()
        postgres_cur = postgres_conn.cursor()
        
        sqlite_cur.execute("""
            SELECT session_id, physician_username, physician_name, approved_at
            FROM approvals
        """)
        
        rows = sqlite_cur.fetchall()
        if not rows:
            logger.info("No approvals to migrate")
            return 0
        
        migrated = 0
        for row in rows:
            old_session_id = row[0]
            new_session_id = self.id_mapping.get('consultations', {}).get(old_session_id)
            
            if not new_session_id:
                continue
            
            postgres_cur.execute("""
                INSERT INTO approvals
                (session_id, physician_username, physician_name, approved_at)
                VALUES (%s, %s, %s, %s)
            """, (new_session_id,) + row[1:])
            migrated += 1
        
        postgres_conn.commit()
        logger.info(f"Migrated {migrated} approvals")
        return migrated
    
    def verify_migration(self, sqlite_conn, postgres_conn) -> bool:
        """Verify migration completed successfully"""
        logger.info("Verifying migration...")
        
        tables = [
            'consultations', 'soap_notes', 'diagnoses', 'provenance_records',
            'retrieved_guidelines', 'qa_results', 'safety_results',
            'lab_values', 'approvals'
        ]
        
        all_match = True
        for table in tables:
            sqlite_count = sqlite_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            postgres_cur = postgres_conn.cursor()
            postgres_cur.execute(f"SELECT COUNT(*) FROM {table}")
            postgres_count = postgres_cur.fetchone()[0]
            
            match = sqlite_count == postgres_count
            status = "✓" if match else "✗"
            logger.info(f"{status} {table}: SQLite={sqlite_count}, PostgreSQL={postgres_count}")
            
            if not match:
                all_match = False
        
        return all_match
    
    def run_migration(self) -> bool:
        """Run complete migration"""
        logger.info("Starting migration from SQLite to PostgreSQL...")
        logger.info(f"SQLite: {self.sqlite_path}")
        logger.info(f"PostgreSQL: {self.postgres_conn_string}")
        
        try:
            sqlite_conn = self.connect_sqlite()
            postgres_conn = self.connect_postgres()
            
            # Migrate in order of dependencies
            self.migrate_consultations(sqlite_conn, postgres_conn)
            self.migrate_soap_notes(sqlite_conn, postgres_conn)
            self.migrate_diagnoses(sqlite_conn, postgres_conn)
            self.migrate_provenance_records(sqlite_conn, postgres_conn)
            self.migrate_retrieved_guidelines(sqlite_conn, postgres_conn)
            self.migrate_qa_results(sqlite_conn, postgres_conn)
            self.migrate_safety_results(sqlite_conn, postgres_conn)
            self.migrate_lab_values(sqlite_conn, postgres_conn)
            self.migrate_approvals(sqlite_conn, postgres_conn)
            
            # Verify
            success = self.verify_migration(sqlite_conn, postgres_conn)
            
            sqlite_conn.close()
            postgres_conn.close()
            
            if success:
                logger.info("✓ Migration completed successfully!")
            else:
                logger.error("✗ Migration completed with errors - counts don't match")
            
            return success
            
        except Exception as e:
            logger.error(f"Migration failed: {e}", exc_info=True)
            return False


def main():
    """Main migration entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Migrate MedScribe data from SQLite to PostgreSQL')
    parser.add_argument('--sqlite', default='data/medscribe.db', help='Path to SQLite database')
    parser.add_argument('--postgres', required=True, help='PostgreSQL connection string')
    
    args = parser.parse_args()
    
    migrator = DatabaseMigrator(args.sqlite, args.postgres)
    success = migrator.run_migration()
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()

# Made with Bob
