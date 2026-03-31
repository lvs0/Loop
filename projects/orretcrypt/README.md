# OrretCrypt

**Post-Quantum Encryption** — Simple, secure, for everyone.

OrretCrypt encrypts files with **ML-KEM-768 (Kyber-768)** + AES-256-GCM. Kyber is the NIST-standardized post-quantum KEM, resistant to quantum computers. The `.orret` format is versioned — future KEM upgrades won't break existing files.

```
# Install
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Generate keys
python3 -m orretcrypt keygen --dir ./keys

# Encrypt
python3 -m orretcrypt encrypt --key keys/orretpub.pem --file doc.pdf

# Decrypt
python3 -m orretcrypt decrypt --key keys/orretpriv.pem --file doc.pdf.orret
```

## Why OrretCrypt

| | OrretCrypt | age | GPG | BitLocker |
|-|-----------|-----|-----|-----------|
| **Post-quantum (Kyber-768)** | ✅ NIST PQC | ❌ | ❌ | ❌ |
| Format: `.orret` | ✅ | `.age` | `.gpg` | proprietary |
| Web app (offline) | ✅ | ❌ | ❌ | ❌ |
| Python library | ✅ | partial | ✅ | ❌ |
| Zero-config | ✅ | ✅ | ❌ | n/a |
| IND-CCA2 secure | ✅ | ✅ | ✅ | ✅ |

## Install

```bash
git clone https://github.com/orretter/orretcrypt
cd orretcrypt
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

**Or use the web version instantly** — drag & drop, no install:
```
Open ~/soe/projects/orretcrypt/index.html in any browser
```

## Quick Start

```bash
# 1. Generate a key pair (1184-byte public, 2400-byte private)
python3 -m orretcrypt keygen --dir ~/keys

# 2. Encrypt any file → .orret format
python3 -m orretcrypt encrypt --key ~/keys/orretpub.pem --file report.pdf

# 3. Decrypt (you need your private key)
python3 -m orretcrypt decrypt --key ~/keys/orretpriv.pem --file report.pdf.orret

# 4. Inspect without decrypting
python3 -m orretcrypt info --file report.pdf.orret
```

## Python API

```python
from orretcrypt import KeyPair, encrypt_file, decrypt_file, info

# Generate ML-KEM-768 keypair
kp = KeyPair.generate()
kp.save_public("pub.pem")
kp.save_private("priv.pem")

# Encrypt / Decrypt
encrypt_file(kp.public_key, "doc.pdf", "doc.pdf.orret")
decrypt_file(kp.private_key, "doc.pdf.orret", "doc.pdf")

# Inspect metadata (no decryption needed)
meta = info("doc.pdf.orret")
print(meta["kem"])  # "ML-KEM-768 (Kyber-768)"
```

## Security

- **IND-CCA2 secure** — Hybrid: Kyber-768 key encapsulation + AES-256-GCM authenticated encryption
- **Post-quantum** — Kyber-768 is NIST PQC standard, ~192-bit classical security, resistant to quantum attacks
- **Authenticated encryption** — AES-GCM provides confidentiality + integrity + authentication
- **HKDF-SHA-512** — NIST standard key derivation from Kyber shared secret
- **Format versioned** — `.orret` header specifies KEM type; future upgrades transparent
- **Browser: pure Web Crypto** — Nothing leaves your device; all processing local

## Architecture

```
.orret file format (v1)
├── magic       4 bytes  — "ORRE" (0x4F 0x52 0x52 0x45)
├── version     1 byte   — 0x01
├── kem_type    1 byte   — 0x02 (Kyber-768)
├── Kem_pk    1184 bytes  — Kyber-768 public key
├── Kem_ct    1088 bytes  — Kyber-768 ciphertext
├── nonce       12 bytes  — AES-GCM nonce
└── ciphertext   N bytes  — AES-256-GCM ciphertext + 16-byte tag
```

## Roadmap

- [x] v1 — ML-KEM-768 + AES-256-GCM CLI + Web (current)
- [ ] v2 — SSH agent integration
- [ ] v2 — Key sharing / re-encapsulation
- [ ] v3 — Desktop GUI (Tauri)
- [ ] v4 — Browser extension + VS Code plugin
- [ ] v5 — Mobile apps

## License

MIT — Orretter (Synapse 🧠)
