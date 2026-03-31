"""
OrretCrypt — Bibliothèque Python
===============================

Chiffrement post-quantique: ML-KEM-768 + AES-256-GCM

Usage:
    from orretcrypt import KeyPair, encrypt_bytes, decrypt_bytes

    kp = KeyPair.generate()
    ct = encrypt_bytes(kp.public_key, b"Secret data!")
    pt = decrypt_bytes(kp.private_key, ct)
"""

from ._orretcrypt_core import (
    KeyPair,
    encrypt_bytes,
    decrypt_bytes,
    encrypt_file,
    decrypt_file,
    info,
    ORRET_MAGIC,
    ORRET_VERSION,
    KEM_TYPE_KYBER768,
    OrretCryptError,
)

__version__ = "1.0.0"
__all__ = [
    "KeyPair",
    "encrypt_bytes",
    "decrypt_bytes",
    "encrypt_file",
    "decrypt_file",
    "info",
    "ORRET_MAGIC",
    "ORRET_VERSION",
    "KEM_TYPE_KYBER768",
    "OrretCryptError",
]
