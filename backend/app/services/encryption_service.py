"""AES-256-GCM field-level encryption for PHI data."""

from __future__ import annotations

import base64
import json
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings


class EncryptionService:
    """Encrypt / decrypt individual fields or JSON payloads using AES-256-GCM.

    Every call generates a unique 96-bit nonce so identical plaintexts produce
    different ciphertexts.  The nonce is prepended to the ciphertext before
    base64-encoding so that ``decrypt_field`` can recover it transparently.
    """

    def __init__(self) -> None:
        key_bytes = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
        if len(key_bytes) != 32:
            raise ValueError(
                "ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256"
            )
        self._aesgcm = AESGCM(key_bytes)

    # ------------------------------------------------------------------
    # String fields
    # ------------------------------------------------------------------

    def encrypt_field(self, plaintext: str) -> str:
        """Encrypt *plaintext* and return a URL-safe base64 string.

        Stored format: ``base64(nonce ‖ ciphertext ‖ tag)``.
        """
        nonce = os.urandom(12)  # 96-bit nonce required by GCM
        ct = self._aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.urlsafe_b64encode(nonce + ct).decode("ascii")

    def decrypt_field(self, ciphertext: str) -> str:
        """Decrypt a value produced by :meth:`encrypt_field`."""
        raw = base64.urlsafe_b64decode(ciphertext)
        if len(raw) < 12:
            raise ValueError("Ciphertext too short to contain a valid nonce")
        nonce, ct = raw[:12], raw[12:]
        return self._aesgcm.decrypt(nonce, ct, None).decode("utf-8")

    # ------------------------------------------------------------------
    # JSON payloads
    # ------------------------------------------------------------------

    def encrypt_json(self, data: dict) -> str:
        """Serialize *data* as compact JSON, then encrypt."""
        return self.encrypt_field(json.dumps(data, separators=(",", ":")))

    def decrypt_json(self, ciphertext: str) -> dict:
        """Decrypt and deserialize a JSON payload."""
        return json.loads(self.decrypt_field(ciphertext))
