"""AES-256-GCM PNR encryption/decryption."""
import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _get_key() -> bytes:
    from ..shared.settings import settings
    raw = settings.pnr_encryption_key
    key_bytes = base64.b64decode(raw)
    if len(key_bytes) != 32:
        raise ValueError("PNR_ENCRYPTION_KEY must be 32 bytes (base64-encoded)")
    return key_bytes


def encrypt_pnr(pnr: str) -> str:
    """Encrypt PNR and return base64(nonce + ciphertext)."""
    key = _get_key()
    nonce = os.urandom(12)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, pnr.encode(), None)
    return base64.b64encode(nonce + ciphertext).decode()


def decrypt_pnr(encrypted: str) -> str:
    """Decrypt a base64(nonce + ciphertext) string back to a PNR."""
    key = _get_key()
    raw = base64.b64decode(encrypted)
    nonce, ciphertext = raw[:12], raw[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None).decode()
