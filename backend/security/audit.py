"""Audit logging for compliance and security tracking."""

import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from backend.security.encryption import scrub_phi_from_logs

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logger for tracking all PHI access and modifications."""
    
    def __init__(self):
        """Initialize audit logger."""
        self.audit_log_file = "logs/audit.log"
        self._setup_audit_logger()
    
    def _setup_audit_logger(self):
        """Setup dedicated audit log file."""
        audit_logger = logging.getLogger("audit")
        audit_logger.setLevel(logging.INFO)
        
        # Create file handler for audit logs
        import os
        os.makedirs("logs", exist_ok=True)
        
        handler = logging.FileHandler(self.audit_log_file)
        handler.setLevel(logging.INFO)
        
        # Format: timestamp | username | action | resource | details
        formatter = logging.Formatter(
            '%(asctime)s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        
        audit_logger.addHandler(handler)
        self.audit_logger = audit_logger
    
    async def log_action(
        self,
        physician_username: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        session_id: Optional[UUID] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Log an audit event.
        
        Args:
            physician_username: Username of the physician performing the action
            action: Action being performed (e.g., 'consultation_created', 'soap_approved')
            resource_type: Type of resource (e.g., 'consultation', 'soap_note')
            resource_id: ID of the resource
            session_id: Consultation session ID
            ip_address: IP address of the request
            user_agent: User agent string
            details: Additional details about the action
        """
        # Scrub PHI from details before logging
        safe_details = scrub_phi_from_logs(details) if details else {}
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "physician_username": physician_username,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "session_id": str(session_id) if session_id else None,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "details": safe_details,
        }
        
        # Log to audit file
        self.audit_logger.info(
            f"{physician_username} | {action} | {resource_type}:{resource_id} | {safe_details}"
        )
        
        # Also store in database for querying
        try:
            await self._store_in_database(log_entry)
        except Exception as e:
            logger.error(f"Failed to store audit log in database: {e}")
    
    async def _store_in_database(self, log_entry: Dict[str, Any]):
        """Store audit log entry in database."""
        from backend.database.postgres_connection import get_session
        from sqlalchemy import text
        
        async with get_session() as session:
            query = text("""
                INSERT INTO audit_log (
                    session_id, physician_username, action, resource_type,
                    resource_id, ip_address, user_agent, details, created_at
                ) VALUES (
                    :session_id, :physician_username, :action, :resource_type,
                    :resource_id, :ip_address, :user_agent, :details::jsonb, :created_at
                )
            """)
            
            await session.execute(query, {
                "session_id": log_entry["session_id"],
                "physician_username": log_entry["physician_username"],
                "action": log_entry["action"],
                "resource_type": log_entry["resource_type"],
                "resource_id": log_entry["resource_id"],
                "ip_address": log_entry["ip_address"],
                "user_agent": log_entry["user_agent"],
                "details": log_entry["details"],
                "created_at": log_entry["timestamp"],
            })
    
    async def log_consultation_created(
        self,
        physician_username: str,
        session_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log consultation creation."""
        await self.log_action(
            physician_username=physician_username,
            action="consultation_created",
            resource_type="consultation",
            resource_id=str(session_id),
            session_id=session_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    async def log_soap_generated(
        self,
        physician_username: str,
        session_id: UUID,
        confidence: float,
        ip_address: Optional[str] = None,
    ):
        """Log SOAP note generation."""
        await self.log_action(
            physician_username=physician_username,
            action="soap_generated",
            resource_type="soap_note",
            resource_id=str(session_id),
            session_id=session_id,
            ip_address=ip_address,
            details={"confidence": confidence},
        )
    
    async def log_soap_approved(
        self,
        physician_username: str,
        session_id: UUID,
        ip_address: Optional[str] = None,
    ):
        """Log SOAP note approval."""
        await self.log_action(
            physician_username=physician_username,
            action="soap_approved",
            resource_type="soap_note",
            resource_id=str(session_id),
            session_id=session_id,
            ip_address=ip_address,
        )
    
    async def log_phi_access(
        self,
        physician_username: str,
        session_id: UUID,
        access_type: str,
        ip_address: Optional[str] = None,
    ):
        """Log PHI access."""
        await self.log_action(
            physician_username=physician_username,
            action="phi_accessed",
            resource_type="consultation",
            resource_id=str(session_id),
            session_id=session_id,
            ip_address=ip_address,
            details={"access_type": access_type},
        )
    
    async def log_login(
        self,
        physician_username: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ):
        """Log login attempt."""
        await self.log_action(
            physician_username=physician_username,
            action="login_success" if success else "login_failed",
            resource_type="auth",
            ip_address=ip_address,
            user_agent=user_agent,
        )
    
    async def log_logout(
        self,
        physician_username: str,
        ip_address: Optional[str] = None,
    ):
        """Log logout."""
        await self.log_action(
            physician_username=physician_username,
            action="logout",
            resource_type="auth",
            ip_address=ip_address,
        )
    
    async def get_audit_trail(
        self,
        session_id: Optional[UUID] = None,
        physician_username: Optional[str] = None,
        action: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100,
    ) -> list:
        """
        Query audit trail.
        
        Args:
            session_id: Filter by session ID
            physician_username: Filter by physician
            action: Filter by action type
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum number of records to return
            
        Returns:
            List of audit log entries
        """
        from backend.database.postgres_connection import get_session
        from sqlalchemy import text
        
        conditions = []
        params: Dict[str, Any] = {"limit": limit}
        
        if session_id:
            conditions.append("session_id = :session_id")
            params["session_id"] = str(session_id)
        
        if physician_username:
            conditions.append("physician_username = :physician_username")
            params["physician_username"] = physician_username
        
        if action:
            conditions.append("action = :action")
            params["action"] = action
        
        if start_date:
            conditions.append("created_at >= :start_date")
            params["start_date"] = start_date
        
        if end_date:
            conditions.append("created_at <= :end_date")
            params["end_date"] = end_date
        
        where_clause = " AND ".join(conditions) if conditions else "1=1"
        
        query = text(f"""
            SELECT * FROM audit_log
            WHERE {where_clause}
            ORDER BY created_at DESC
            LIMIT :limit
        """)
        
        async with get_session() as session:
            result = await session.execute(query, params)
            return [dict(row) for row in result.fetchall()]


# Global audit logger instance
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Get or create global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger

# Made with Bob
