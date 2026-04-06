# OrretCrypt Build Log — 2026-03-31

## Status: ✅ PHASE 1 COMPLETE

---

## Research Findings

### Post-Quantum Cryptography
- **ML-KEM-768 (Kyber-768)**: NIST PQC standard, ~192-bit security, 1184 byte public key, 2400 byte private key, 1088 byte ciphertext
- **ML-DSA (Dilithium)**: Digital signatures, not needed for v1 encryption
- **Kyber libraries**: `kyber-py` (pure Python) works but has quirks with API naming

### Library Compatibility
- `cryptography` (system): v41.0.7 — NO Kyber support
- `cryptography` (venv): v46.0.6 — NO Kyber built-in
- `kyber-py` v1.2.0: Works! ML-KEM-768 functional
  - Note: `encaps()` returns `(shared_secret, ciphertext)` NOT `(ciphertext, shared_secret)`
  - `decaps(private_key, ct_kem)` returns shared secret
- `pqcrypto`: No pre-built wheels, build issues

### Format Design
- `.orret` v1: `magic(4) + version(1) + kem(1) + pk_len(2) + ct_kem_len(2) + pk + ct_kem + nonce(12) + tag(16) + ct`
- Hybrid: Kyber for KEM + AES-256-GCM for data
- HKDF-SHA-512 for key derivation from Kyber shared secret

---

## Deliverables

### 1. SPEC.md ✅
- Architecture, format spec, CLI structure, roadmap

### 2. orretcrypt.py (CLI) ✅
- `keygen`, `encrypt`, `decrypt`, `info` commands
- Colored terminal output
- PEM key storage
- Proper error handling

### 3. _orretcrypt_core.py ✅
- ML-KEM-768 keygen, encaps, decaps
- AES-256-GCM encryption
- HKDF-SHA-512 key derivation
- .orret format v1
- encrypt_bytes, decrypt_bytes, encrypt_file, decrypt_file, info()

### 4. __init__.py ✅
- Clean library import API

### 5. index.html (Web App) ✅
- Single file, works offline
- ECDH P-256 + AES-256-GCM (browser limitation)
- Drag & drop UI
- Glassmorphism dark theme
- LocalStorage key persistence

### 6. README.md ✅
- Installation instructions
- Use cases
- Security explanation
- Roadmap

### 7. requirements.txt ✅
### 8. install.sh ✅

---

## Issues Encountered

1. **kyber-py API naming**: `encaps()` returns `(shared_secret, ciphertext)` — easy to confuse order
2. **System cryptography too old**: No Kyber built-in, needed venv
3. **kyber-py v1 API**: Initially tried `(ct, ss) = encaps()` which was wrong — should be `(ss, ct)`
4. **Format revision**: Initial `encrypt()` function had a bug where Kyber ciphertext wasn't stored — fixed by adding `ct_kem_len` field

---

## Next Steps (v2+)
- [ ] Key sharing (re-encapsulation)
- [ ] Passphrase protection for private keys (Argon2id)
- [ ] Multi-recipient encryption
- [ ] Desktop GUI (Tauri)
- [ ] Native Kyber in web (WASM)
- [ ] Browser extension

---

## Final Project Structure

```
orretcrypt/
├── orretcrypt/          # Python package
│   ├── __init__.py      # Library exports
│   ├── __main__.py      # Entry point: python3 -m orretcrypt
│   ├── _orretcrypt_core.py  # Core crypto implementation
│   └── cli.py            # CLI commands
├── index.html           # Web app (single file, offline)
├── README.md
├── SPEC.md
├── requirements.txt
├── pyproject.toml       # Installable package
├── install.sh           # Installation script
└── .venv/              # Python venv
```

## Test Results
```
KeyGen: ✅ PK=1184B SK=2400B
Encrypt/Decrypt: ✅ Small (1250→3560B)
Large (10MB): ✅ Roundtrip OK
File I/O: ✅
Header format: ✅ Magic=ORRE Version=1 KEM=Kyber-768
CLI: ✅ keygen/encrypt/decrypt/info all working
```

---

*Built by Synapse 🧠 — 2026-03-31*
