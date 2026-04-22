import base64
import hashlib

from cryptography.fernet import Fernet
from django.conf import settings


def _build_fernet() -> Fernet:
    """
    Build Fernet instance with proper key derivation.
    
    TOKEN_ENCRYPTION_KEY can be:
    - Empty/not set: use derived key from SECRET_KEY (dev only)
    - Any string: hash it to get 32 bytes, then base64-encode for Fernet
    """
    raw_key = settings.TOKEN_ENCRYPTION_KEY.strip() if settings.TOKEN_ENCRYPTION_KEY else ""
    
    if raw_key:
        # User provided a key: hash it to get exactly 32 bytes
        digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
        derived_key = base64.urlsafe_b64encode(digest)
        return Fernet(derived_key)
    else:
        # Dev fallback: derive from SECRET_KEY
        digest = hashlib.sha256(settings.SECRET_KEY.encode("utf-8")).digest()
        derived_key = base64.urlsafe_b64encode(digest)
        return Fernet(derived_key)


def encrypt_token(token: str) -> str:
    """Encrypt API token using Fernet symmetric encryption."""
    fernet = _build_fernet()
    return fernet.encrypt(token.encode("utf-8")).decode("utf-8")


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt API token using Fernet symmetric encryption."""
    fernet = _build_fernet()
    return fernet.decrypt(encrypted_token.encode("utf-8")).decode("utf-8")

