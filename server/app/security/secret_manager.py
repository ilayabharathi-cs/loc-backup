"""Cryptographic Secret Management abstraction for RetroVault V7."""

import os
import base64
import hashlib
import hmac
import json
from typing import Optional, Dict, Any
from app.config import settings


class SecretManager:
    """Provides secure encryption and masking of repository credentials, tokens, and secrets."""

    def __init__(self, master_key: Optional[str] = None):
        raw_key = master_key or getattr(settings, "SECRET_KEY", "retrovault_master_enterprise_secret_key_v7")
        self._key = hashlib.sha256(raw_key.encode("utf-8")).digest()

    def encrypt_secret(self, plaintext: str) -> str:
        """Encrypts a plaintext secret string and returns a base64 encoded payload."""
        if not plaintext:
            return ""
        salt = os.urandom(16)
        derived_key = hashlib.pbkdf2_hmac("sha256", self._key, salt, 10000)
        # Keystream generation via HMAC-SHA256 counter
        data = plaintext.encode("utf-8")
        keystream = bytearray()
        counter = 0
        while len(keystream) < len(data):
            counter += 1
            keystream.extend(hmac.new(derived_key, counter.to_bytes(4, "big"), hashlib.sha256).digest())
        encrypted = bytes(d ^ k for d, k in zip(data, keystream[:len(data)]))
        tag = hmac.new(derived_key, encrypted, hashlib.sha256).digest()[:16]

        payload = {
            "v": 1,
            "salt": base64.b64encode(salt).decode("utf-8"),
            "data": base64.b64encode(encrypted).decode("utf-8"),
            "tag": base64.b64encode(tag).decode("utf-8")
        }
        return "enc:" + base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")

    def decrypt_secret(self, ciphertext: str) -> str:
        """Decrypts a base64 encoded ciphertext payload back to plaintext."""
        if not ciphertext:
            return ""
        if not ciphertext.startswith("enc:"):
            # Plaintext fallback for legacy/unencrypted development strings
            return ciphertext

        raw_json = base64.b64decode(ciphertext[4:]).decode("utf-8")
        payload = json.loads(raw_json)
        salt = base64.b64decode(payload["salt"])
        encrypted = base64.b64decode(payload["data"])
        expected_tag = base64.b64decode(payload["tag"])

        derived_key = hashlib.pbkdf2_hmac("sha256", self._key, salt, 10000)
        computed_tag = hmac.new(derived_key, encrypted, hashlib.sha256).digest()[:16]
        if not hmac.compare_digest(expected_tag, computed_tag):
            raise ValueError("Secret decryption integrity check failed")

        keystream = bytearray()
        counter = 0
        while len(keystream) < len(encrypted):
            counter += 1
            keystream.extend(hmac.new(derived_key, counter.to_bytes(4, "big"), hashlib.sha256).digest())
        decrypted = bytes(e ^ k for e, k in zip(encrypted, keystream[:len(encrypted)]))
        return decrypted.decode("utf-8")

    def mask_secret(self, secret: str) -> str:
        """Masks sensitive credentials for API presentation."""
        if not secret:
            return "******"
        if len(secret) <= 6:
            return "******"
        return f"{secret[:2]}****{secret[-2:]}"


# Global singleton instance
_secret_manager = None

def get_secret_manager() -> SecretManager:
    global _secret_manager
    if _secret_manager is None:
        _secret_manager = SecretManager()
    return _secret_manager
