"""
OrretCrypt Core — Hybrid Post-Quantum Encryption Engine
=======================================================
• ML-KEM-768 (Kyber-768) + AES-256-GCM  ← Phase 1
• Format: .orret v1

Format header: versioned, KEM type in header for future upgrades.
"""

import os
import struct
import hashlib
from typing import Tuple

# ─── Constants ───────────────────────────────────────────
ORRET_MAGIC = b"ORRE"           # 0x4F 0x52 0x52 0x45
ORRET_VERSION = 0x01
KEM_TYPE_KYBER768 = 0x02        # ML-KEM-768 (Kyber-768)
NONCE_SIZE = 12                  # AES-GCM nonce
TAG_SIZE = 16                   # AES-GCM tag

# ─── Kyber import ───────────────────────────────────────
try:
    from kyber_py.ml_kem import ML_KEM_768 as _KYBER
    _HAS_KYBER = True
except ImportError:
    _HAS_KYBER = False
    raise ImportError(
        "kyber_py requis. Installez avec:\n"
        "  python3 -m venv .venv && source .venv/bin/activate && pip install kyber-py cryptography"
    )

# ─── AES-GCM via cryptography ───────────────────────────
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class OrretCryptError(Exception):
    """Base exception."""


def _derive_aes_key(shared_secret: bytes) -> Tuple[bytes, bytes]:
    """
    HKDF-SHA-512 to derive AES key + salt from Kyber shared secret.
    Returns (aes_key_256, salt_128).
    """
    hkdf = HKDF(
        algorithm=hashes.SHA512(),
        length=48,
        salt=os.urandom(32),
        info=b'orretcrypt-v1',
    )
    derived = hkdf.derive(shared_secret + b'orretcrypt-kdf-salt')
    return derived[:32], derived[32:48]


# ─── Key Pair ────────────────────────────────────────────
class KeyPair:
    """
    ML-KEM-768 Key Pair.
    
    Attributes:
        public_key:  1184 bytes — encapsulation key
        private_key: 2400 bytes — decapsulation key
    """
    
    def __init__(self, public_key: bytes, private_key: bytes):
        if len(public_key) != 1184:
            raise OrretCryptError(f"PK doit faire 1184 octets, reçu: {len(public_key)}")
        if len(private_key) != 2400:
            raise OrretCryptError(f"SK doit faire 2400 octets, reçu: {len(private_key)}")
        self.public_key = public_key
        self.private_key = private_key
    
    @classmethod
    def generate(cls) -> 'KeyPair':
        """Génère une nouvelle clépair ML-KEM-768."""
        pk, sk = _KYBER.keygen()
        return cls(pk, sk)
    
    def save_public(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.public_key)
    
    def save_private(self, path: str):
        with open(path, 'wb') as f:
            f.write(self.private_key)
    
    @classmethod
    def load_public(cls, path: str) -> 'KeyPair':
        with open(path, 'rb') as f:
            data = f.read()
        if len(data) == 1184:
            return cls(data, b'\x00' * 2400)  # dummy sk
        # Try PEM
        if b'BEGIN' in data:
            import base64
            lines = [l for l in data.decode().split('\n') if not l.startswith('-----')]
            data = base64.b64decode(''.join(lines))
        return cls(data[:1184], b'\x00' * 2400)
    
    @classmethod
    def load_private(cls, path: str) -> 'KeyPair':
        with open(path, 'rb') as f:
            data = f.read()
        if len(data) == 2400:
            return cls(b'\x00' * 1184, data)  # dummy pk
        if b'BEGIN' in data:
            import base64
            lines = [l for l in data.decode().split('\n') if not l.startswith('-----')]
            data = base64.b64decode(''.join(lines))
        return cls(b'\x00' * 1184, data[:2400])


def encrypt_bytes(public_key: bytes, plaintext: bytes) -> bytes:
    """
    Chiffre des données avec ML-KEM-768 + AES-256-GCM.
    
    Format .orret v1:
      magic(4) + version(1) + kem(1) + pk_len(2) + ct_kem_len(2)
      + public_key(pk_len) + ct_kem(ct_kem_len)
      + nonce(12) + tag(16) + ciphertext(N)
    """
    if len(public_key) != 1184:
        raise OrretCryptError(f"PK doit faire 1184 octets, reçu: {len(public_key)}")
    
    # 1. Kyber encapsulation → shared secret + ciphertext
    ss, ct_kem = _KYBER.encaps(public_key)
    # ss=32 bytes, ct_kem=1088 bytes
    
    # 2. Derive AES-256 key via HKDF-SHA-512
    aes_key_raw = hashlib.sha512(ss + b'orretcrypt-v1').digest()[:32]
    salt_val = hashlib.sha512(ss + b'orretcrypt-salt').digest()[:16]
    aesgcm = AESGCM(aes_key_raw)
    
    # 3. AES-GCM encryption
    nonce = os.urandom(12)
    aad = ORRET_MAGIC + bytes([ORRET_VERSION, KEM_TYPE_KYBER768])
    full_ct = aesgcm.encrypt(nonce, plaintext, aad)
    actual_ct = full_ct[:-16]
    tag = full_ct[-16:]
    
    # 4. Build .orret file
    result = bytearray()
    result.extend(ORRET_MAGIC)
    result.append(ORRET_VERSION)
    result.append(KEM_TYPE_KYBER768)
    result.extend(struct.pack('>H', len(public_key)))
    result.extend(struct.pack('>H', len(ct_kem)))
    result.extend(public_key)
    result.extend(ct_kem)
    result.extend(nonce)
    result.extend(tag)
    result.extend(actual_ct)
    
    return bytes(result)


def decrypt_bytes(private_key: bytes, data: bytes) -> bytes:
    """
    Déchiffre un fichier .orret.
    """
    if len(private_key) != 2400:
        raise OrretCryptError(f"SK doit faire 2400 octets, reçu: {len(private_key)}")
    
    min_len = 4 + 1 + 1 + 2 + 2 + 1184 + 1088 + 12 + 16 + 1
    if len(data) < min_len:
        raise OrretCryptError(f"Données trop courtes: {len(data)} < {min_len}")
    
    magic = data[:4]
    if magic != ORRET_MAGIC:
        raise OrretCryptError(f"Magic bytes invalides: {magic.hex()}")
    
    version = data[4]
    kem_type = data[5]
    pk_len = struct.unpack('>H', data[6:8])[0]
    ct_kem_len = struct.unpack('>H', data[8:10])[0]
    
    offset = 10
    offset += pk_len  # skip stored pk
    ct_kem = data[offset:offset + ct_kem_len]
    offset += ct_kem_len
    nonce = data[offset:offset + 12]
    offset += 12
    tag = data[offset:offset + 16]
    offset += 16
    encrypted_data = data[offset:]
    
    # Decapsulate Kyber to get shared secret
    ss = _KYBER.decaps(private_key, ct_kem)
    
    # Derive AES key
    aes_key_raw = hashlib.sha512(ss + b'orretcrypt-v1').digest()[:32]
    aesgcm = AESGCM(aes_key_raw)
    
    # Decrypt
    aad = ORRET_MAGIC + bytes([ORRET_VERSION, KEM_TYPE_KYBER768])
    full_ct = encrypted_data + tag
    
    try:
        plaintext = aesgcm.decrypt(nonce, full_ct, aad)
    except Exception as e:
        raise OrretCryptError(f"Échec déchiffrement AES-GCM: {e}")
    
    return plaintext


def encrypt_file(public_key: bytes, input_path: str, output_path: str = None):
    """Chiffre un fichier."""
    with open(input_path, 'rb') as f:
        pt = f.read()
    ct = encrypt_bytes(public_key, pt)
    out = output_path or (input_path + '.orret')
    with open(out, 'wb') as f:
        f.write(ct)
    return out


def decrypt_file(private_key: bytes, input_path: str, output_path: str = None):
    """Déchiffre un fichier."""
    with open(input_path, 'rb') as f:
        data = f.read()
    pt = decrypt_bytes(private_key, data)
    out = output_path or input_path.replace('.orret', '') + '.decrypted'
    if out == input_path:
        out = input_path + '.decrypted'
    with open(out, 'wb') as f:
        f.write(pt)
    return out


def info(ciphertext_path: str) -> dict:
    """Retourne les métadonnées d'un fichier .orret."""
    with open(ciphertext_path, 'rb') as f:
        data = f.read()
    
    magic = data[:4]
    version = data[4]
    kem_type = data[5]
    pk_len = struct.unpack('>H', data[6:8])[0]
    ct_kem_len = struct.unpack('>H', data[8:10])[0]
    nonce_len = 12
    tag_len = 16
    header_len = 10
    ct_len = len(data) - header_len - pk_len - ct_kem_len - nonce_len - tag_len
    
    kem_names = {0x01: 'X25519', 0x02: 'Kyber-768'}
    
    return {
        'magic': magic.hex(),
        'version': version,
        'kem_type': kem_type,
        'kem_name': kem_names.get(kem_type, f'Inconnu(0x{kem_type:02x})'),
        'pk_len': pk_len,
        'ct_kem_len': ct_kem_len,
        'ct_len': ct_len,
        'total_len': len(data),
    }


# ─── Aliases for CLI compatibility ───────────────────────
encrypt = encrypt_bytes
decrypt = decrypt_bytes
