"""Data encryption utilities for PHI protection at rest."""

import base64
import logging
import os
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)


class EncryptionService:
    """Service for encrypting and decrypting sensitive data."""
    
    def __init__(self, encryption_key: Optional[str] = None):
        """
        Initialize encryption service.
        
        Args:
            encryption_key: Base64-encoded Fernet key. If None, reads from environment.
        """
        if encryption_key is None:
            encryption_key = os.getenv("ENCRYPTION_KEY")
        
        if not encryption_key:
            logger.warning("No encryption key provided. Generating temporary key (NOT FOR PRODUCTION!)")
            encryption_key = Fernet.generate_key().decode()
        
        try:
            self.fernet = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
            logger.info("Encryption service initialized")
        except Exception as e:
            logger.error(f"Failed to initialize encryption service: {e}")
            raise ValueError("Invalid encryption key") from e
    
    def encrypt(self, data: str) -> str:
        """
        Encrypt string data.
        
        Args:
            data: Plain text string to encrypt
            
        Returns:
            Base64-encoded encrypted string
        """
        try:
            encrypted_bytes = self.fernet.encrypt(data.encode('utf-8'))
            return base64.b64encode(encrypted_bytes).decode('utf-8')
        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise
    
    def decrypt(self, encrypted_data: str) -> str:
        """
        Decrypt encrypted string data.
        
        Args:
            encrypted_data: Base64-encoded encrypted string
            
        Returns:
            Decrypted plain text string
        """
        try:
            encrypted_bytes = base64.b64decode(encrypted_data.encode('utf-8'))
            decrypted_bytes = self.fernet.decrypt(encrypted_bytes)
            return decrypted_bytes.decode('utf-8')
        except InvalidToken:
            logger.error("Decryption failed: Invalid token or corrupted data")
            raise ValueError("Failed to decrypt data: Invalid encryption key or corrupted data")
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise
    
    def encrypt_dict(self, data: dict) -> dict:
        """
        Encrypt all string values in a dictionary.
        
        Args:
            data: Dictionary with string values
            
        Returns:
            Dictionary with encrypted values
        """
        encrypted = {}
        for key, value in data.items():
            if isinstance(value, str):
                encrypted[key] = self.encrypt(value)
            elif isinstance(value, dict):
                encrypted[key] = self.encrypt_dict(value)
            elif isinstance(value, list):
                encrypted[key] = [self.encrypt(v) if isinstance(v, str) else v for v in value]
            else:
                encrypted[key] = value
        return encrypted
    
    def decrypt_dict(self, encrypted_data: dict) -> dict:
        """
        Decrypt all encrypted values in a dictionary.
        
        Args:
            encrypted_data: Dictionary with encrypted values
            
        Returns:
            Dictionary with decrypted values
        """
        decrypted = {}
        for key, value in encrypted_data.items():
            if isinstance(value, str):
                try:
                    decrypted[key] = self.decrypt(value)
                except Exception:
                    # If decryption fails, assume it's not encrypted
                    decrypted[key] = value
            elif isinstance(value, dict):
                decrypted[key] = self.decrypt_dict(value)
            elif isinstance(value, list):
                decrypted[key] = [
                    self.decrypt(v) if isinstance(v, str) else v 
                    for v in value
                ]
            else:
                decrypted[key] = value
        return decrypted


# Global encryption service instance
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Get or create global encryption service instance."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


def encrypt_phi(data: str) -> str:
    """
    Encrypt Protected Health Information (PHI).
    
    Args:
        data: PHI string to encrypt
        
    Returns:
        Encrypted string
    """
    service = get_encryption_service()
    return service.encrypt(data)


def decrypt_phi(encrypted_data: str) -> str:
    """
    Decrypt Protected Health Information (PHI).
    
    Args:
        encrypted_data: Encrypted PHI string
        
    Returns:
        Decrypted PHI string
    """
    service = get_encryption_service()
    return service.decrypt(encrypted_data)


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key.
    
    Returns:
        Base64-encoded encryption key
    """
    return Fernet.generate_key().decode()


# PHI field detection patterns
PHI_PATTERNS = [
    'patient_name', 'patient_id', 'mrn', 'ssn', 'phone', 'email',
    'address', 'date_of_birth', 'dob', 'medical_record_number'
]


def is_phi_field(field_name: str) -> bool:
    """
    Check if a field name likely contains PHI.
    
    Args:
        field_name: Field name to check
        
    Returns:
        True if field likely contains PHI
    """
    field_lower = field_name.lower()
    return any(pattern in field_lower for pattern in PHI_PATTERNS)


def scrub_phi_from_logs(data: dict) -> dict:
    """
    Remove or mask PHI fields from data before logging.
    
    Args:
        data: Dictionary that may contain PHI
        
    Returns:
        Dictionary with PHI fields masked
    """
    scrubbed = {}
    for key, value in data.items():
        if is_phi_field(key):
            scrubbed[key] = "***REDACTED***"
        elif isinstance(value, dict):
            scrubbed[key] = scrub_phi_from_logs(value)
        elif isinstance(value, list):
            scrubbed[key] = [
                scrub_phi_from_logs(v) if isinstance(v, dict) else v
                for v in value
            ]
        else:
            scrubbed[key] = value
    return scrubbed

# Made with Bob
