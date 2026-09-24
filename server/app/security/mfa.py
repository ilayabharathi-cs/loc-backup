"""TOTP Multi-Factor Authentication (RFC 6238) for RetroVault V7."""

import time
import struct
import hmac
import hashlib
import base64
import secrets
from typing import Tuple, List, Optional


class TotpManager:
    """Standard RFC 6238 Time-based One-Time Password engine."""

    @staticmethod
    def generate_secret() -> str:
        """Generate a random 160-bit (20 bytes) base32 encoded secret."""
        raw = secrets.token_bytes(20)
        return base64.b32encode(raw).decode("utf-8").replace("=", "")

    @staticmethod
    def generate_provisioning_uri(username: str, secret: str, issuer: str = "RetroVault") -> str:
        """Build standard otpauth:// URL for authenticator apps."""
        clean_user = username.strip()
        clean_issuer = issuer.strip()
        return f"otpauth://totp/{clean_issuer}:{clean_user}?secret={secret}&issuer={clean_issuer}&algorithm=SHA1&digits=6&period=30"

    @staticmethod
    def get_totp_code(secret: str, time_step: Optional[int] = None) -> str:
        """Compute the current 6-digit TOTP code for a secret."""
        if time_step is None:
            time_step = int(time.time() // 30)

        # Pad secret if needed
        pad_len = (8 - len(secret) % 8) % 8
        padded_secret = secret + ("=" * pad_len)
        key = base64.b32decode(padded_secret, casefold=True)

        # Counter packed as 8-byte big-endian integer
        msg = struct.pack(">Q", time_step)
        h = hmac.new(key, msg, hashlib.sha1).digest()

        # Dynamic truncation
        offset = h[-1] & 0x0F
        binary = struct.unpack(">I", h[offset:offset + 4])[0] & 0x7FFFFFFF
        code = binary % 1000000
        return f"{code:06d}"

    @classmethod
    def verify_code(cls, secret: str, code: str, window: int = 1) -> bool:
        """Verify code against current time step with +/- window tolerance."""
        if not secret or not code:
            return False
        clean_code = str(code).strip()
        current_step = int(time.time() // 30)

        for step in range(current_step - window, current_step + window + 1):
            if cls.get_totp_code(secret, step) == clean_code:
                return True
        return False

    @staticmethod
    def generate_recovery_codes(count: int = 8) -> List[str]:
        """Generate human-readable recovery codes e.g. 'a1b2-c3d4'."""
        codes = []
        for _ in range(count):
            c = secrets.token_hex(4).upper()
            codes.append(f"{c[:4]}-{c[4:]}")
        return codes

    @staticmethod
    def hash_recovery_code(code: str) -> str:
        """Hash recovery code with SHA-256 for secure database storage."""
        clean = code.replace("-", "").strip().upper()
        return hashlib.sha256(clean.encode("utf-8")).hexdigest()

    @classmethod
    def verify_and_consume_recovery_code(cls, candidate_code: str, hashed_codes: List[str]) -> Tuple[bool, List[str]]:
        """Verify recovery code and return remaining unused hashed codes."""
        candidate_hash = cls.hash_recovery_code(candidate_code)
        for i, h in enumerate(hashed_codes):
            if hmac.compare_digest(h, candidate_hash):
                remaining = [x for idx, x in enumerate(hashed_codes) if idx != i]
                return True, remaining
        return False, hashed_codes
