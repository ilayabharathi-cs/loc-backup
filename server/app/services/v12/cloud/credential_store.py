"""Secure Credential Management for Cloud & Hybrid Storage Tiering."""

import uuid
import logging
from typing import Dict, Any, List, Tuple, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.storage_tier_v12_models import CloudCredential
from app.security.secret_manager import get_secret_manager
from app.services.audit_service import log_audit_event

logger = logging.getLogger(__name__)


class CredentialStoreService:
    """
    Manages secure cloud storage credentials at rest.
    Strictly enforces zero-leakage of access keys and secret keys.
    """

    def __init__(self, db: Session):
        self.db = db
        self.secret_manager = get_secret_manager()

    def create_credential(
        self,
        name: str,
        provider: str,
        access_key: str,
        secret_key: str,
        endpoint: Optional[str] = None,
        region: Optional[str] = "us-east-1",
        prefix: Optional[str] = None,
        use_tls: bool = True,
        verify_ssl: bool = True,
        user_id: Optional[int] = None
    ) -> CloudCredential:
        """
        Encrypts and persists cloud credentials.
        Never logs or exposes access_key or secret_key.
        """
        if not name or not name.strip():
            raise ValueError("Credential name is required")
        if not access_key or not access_key.strip():
            raise ValueError("Access key is required")
        if not secret_key or not secret_key.strip():
            raise ValueError("Secret key is required")

        existing = self.db.scalar(select(CloudCredential).where(CloudCredential.name == name.strip()))
        if existing:
            raise ValueError(f"Credential with name '{name}' already exists")

        # Encrypt sensitive material at rest
        enc_access = self.secret_manager.encrypt_secret(access_key.strip())
        enc_secret = self.secret_manager.encrypt_secret(secret_key.strip())

        cred_id = f"cred_{uuid.uuid4().hex[:12]}"
        cred = CloudCredential(
            credential_id=cred_id,
            name=name.strip(),
            provider=provider.strip().lower(),
            endpoint=endpoint.strip() if endpoint else None,
            region=region.strip() if region else "us-east-1",
            access_key_encrypted=enc_access,
            secret_key_encrypted=enc_secret,
            prefix=prefix.strip() if prefix else None,
            use_tls=use_tls,
            verify_ssl=verify_ssl,
            status="configured"
        )
        self.db.add(cred)
        self.db.commit()
        self.db.refresh(cred)

        # Audit log creation without any secret details
        log_audit_event(
            db=self.db,
            action="CLOUD_CREDENTIAL_CREATE",
            resource_type="CloudCredential",
            resource_id=cred.credential_id,
            user_id=user_id,
            details=f"Created cloud credential '{cred.name}' for provider '{cred.provider}'"
        )

        return cred

    def get_credential_safe(self, identifier: Union[str, int]) -> Dict[str, Any]:
        """
        Retrieve safe public representation of credential.
        Access key is masked, secret key is NEVER returned.
        """
        cred = self._resolve_credential(identifier)
        if not cred:
            raise ValueError(f"Credential '{identifier}' not found")

        raw_access = self.secret_manager.decrypt_secret(cred.access_key_encrypted)
        masked_access = self.secret_manager.mask_secret(raw_access)

        return {
            "id": cred.id,
            "credential_id": cred.credential_id,
            "name": cred.name,
            "provider": cred.provider,
            "endpoint": cred.endpoint,
            "region": cred.region,
            "prefix": cred.prefix,
            "use_tls": cred.use_tls,
            "verify_ssl": cred.verify_ssl,
            "access_key_masked": masked_access,
            "status": cred.status,
            "created_at": cred.created_at,
            "updated_at": cred.updated_at
        }

    def list_credentials_safe(self) -> List[Dict[str, Any]]:
        """
        List all credentials safely with masked access keys and zero secrets.
        """
        creds = self.db.scalars(select(CloudCredential).order_by(CloudCredential.created_at.desc())).all()
        result = []
        for cred in creds:
            try:
                raw_access = self.secret_manager.decrypt_secret(cred.access_key_encrypted)
                masked_access = self.secret_manager.mask_secret(raw_access)
            except Exception:
                masked_access = "******"

            result.append({
                "id": cred.id,
                "credential_id": cred.credential_id,
                "name": cred.name,
                "provider": cred.provider,
                "endpoint": cred.endpoint,
                "region": cred.region,
                "prefix": cred.prefix,
                "use_tls": cred.use_tls,
                "verify_ssl": cred.verify_ssl,
                "access_key_masked": masked_access,
                "status": cred.status,
                "created_at": cred.created_at,
                "updated_at": cred.updated_at
            })
        return result

    def get_decrypted_secrets(self, identifier: Union[str, int]) -> Tuple[str, str]:
        """
        Internal use only by TieringManager.
        Never exposed over APIs, audit logs, or exception traces.
        Returns: (access_key, secret_key)
        """
        cred = self._resolve_credential(identifier)
        if not cred:
            raise ValueError(f"Credential '{identifier}' not found")

        try:
            access_key = self.secret_manager.decrypt_secret(cred.access_key_encrypted)
            secret_key = self.secret_manager.decrypt_secret(cred.secret_key_encrypted)
            return access_key, secret_key
        except Exception as e:
            # Shield exception to prevent leaking encryption details
            raise ValueError("Failed to decrypt cloud storage credentials securely") from None

    def delete_credential(self, identifier: Union[str, int], user_id: Optional[int] = None) -> bool:
        """
        Deletes a credential.
        """
        cred = self._resolve_credential(identifier)
        if not cred:
            raise ValueError(f"Credential '{identifier}' not found")

        cred_name = cred.name
        cred_id = cred.credential_id

        self.db.delete(cred)
        self.db.commit()

        log_audit_event(
            db=self.db,
            action="CLOUD_CREDENTIAL_DELETE",
            resource_type="CloudCredential",
            resource_id=cred_id,
            user_id=user_id,
            details=f"Deleted cloud credential '{cred_name}'"
        )
        return True

    def _resolve_credential(self, identifier: Union[str, int]) -> Optional[CloudCredential]:
        if isinstance(identifier, int) or (isinstance(identifier, str) and identifier.isdigit()):
            cred = self.db.scalar(select(CloudCredential).where(CloudCredential.id == int(identifier)))
            if cred:
                return cred
        return self.db.scalar(select(CloudCredential).where(CloudCredential.credential_id == str(identifier)))
