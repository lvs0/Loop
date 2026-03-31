# OrretCrypt — Spécification Technique

**Version:** 1.0.0  
**Status:** Phase 1 — MVP  
**Auteur:** Synapse 🧠 (Orretter)

---

## 1. Principes Fondamentaux

- **Sécurité d'abord, utilisabilité ensuite** — Pas de compromis sur la crypto
- **Post-quantique** — Résistant aux ordinateurs quantiques (algorithmes NIST PQC)
- **Simple** — Une commande, un résultat. Pas de configuration complexe
- **Multi-plateforme** — Linux, macOS, Windows
- **Hybride** — Combinaison crypto classique + post-quantique

---

## 2. Choix Cryptographique

### Phase 1 (actuel)

| Composant | Algorithme | Raison |
|-----------|-----------|--------|
| Encapsulation de clé (KEM) | **ML-KEM-768** (Kyber-768) | Standard NIST PQC, ~192-bit sécurité |
| Chiffrement symétrique | **AES-256-GCM** | Standard NIST, authentifié |
| Dérivation de clé | **HKDF-SHA-512** | Standard, solide |
| Génération aléatoire | OS CSPRNG (`secrets` / `os.urandom`) | — |

### Hybridation (IND-CCA2 secure)
1. ML-KEM-768 encaps génère un secret partagé de 32 octets
2. HKDF-SHA-512 dérive une clé AES de 256 bits
3. AES-256-GCM chiffre les données avec cette clé
4. Sortie = `(ciphertext_mlkem || nonce || tag_aes || ciphertext_data)`

### Sécurité post-quantique
- ML-KEM-768 est considéré secure contre attaques classiques ET quantiques
- AES-256-GCM est secure contre attaques classiques (Grover's algo nécessiterait 2^128 opérations quantiques)

---

## 3. Format de Fichier `.orret`

```
.orret file structure (v1):
├── magic:          4 bytes  — 0x4F 0x52 0x52 0x45 ("ORRE")
├── version:        1 byte   — 0x01
├── kem_type:       1 byte   — 0x01 (ML-KEM-768)
├── pk_len:         2 bytes — longueur de la clé publique (big-endian)
├── sk_len:         2 bytes — longueur de la clé privée (big-endian)
├── pk:             pk_len bytes — clé publique Kyber (pour encapsulation)
├── sk:             sk_len bytes — clé privée Kyber (pour decapsulation, optionnel)
├── nonce:          12 bytes — nonce AES-GCM
├── tag:            16 bytes — tag AES-GCM
├── ciphertext:     N bytes  — données chiffrées AES-GCM
```

**Note:** Les clés Kyber sont stockées en format brut (bytes), pas PEM, pour simplifier le format.

---

## 4. Structure CLI

```bash
python3 -m orretcrypt keygen [--output-dir <dir>]     # Génère clépair Kyber-768
python3 -m orretcrypt encrypt --key <pub.pem> --file <f> [--output <out.orret>]
python3 -m orretcrypt decrypt --key <priv.pem> --file <f.orret> [--output <out>]
python3 -m orretcrypt share --recipient-key <pub.pem> --my-key <priv.pem> --file <f> [--output <out.orret>]
python3 -m orretcrypt info --file <f.orret>           # Affiche métadonnées
```

### Format de clé PEM
- Clé publique: `-----BEGIN ORRET PUBLIC KEY-----` / `-----END ORRET PUBLIC KEY-----`
- Clé privée: `-----BEGIN ORRET PRIVATE KEY-----` / `-----END ORRET PRIVATE KEY-----`

---

## 5. API Python

```python
from orretcrypt import KeyPair, encrypt, decrypt

# Génération de clépair
kp = KeyPair.generate()  # ML-KEM-768 par défaut
kp.public_key          # bytes
kp.private_key         # bytes
kp.save_public("pub.pem")
kp.save_private("priv.pem")

# Chiffrement
ciphertext = encrypt(public_key, plaintext_bytes)  # -> bytes .orret
ciphertext = encrypt(public_key, plaintext_bytes, file_format=True)  # avec header .orret

# Déchiffrement
plaintext = decrypt(private_key, ciphertext)

# Avec fichiers
encrypt_file(public_key_bytes, "document.pdf", "document.pdf.orret")
decrypt_file(private_key_bytes, "document.pdf.orret", "document.pdf")
```

---

## 6. Web App (index.html)

- **Single file** — Fonctionne hors-ligne
- **Génération de clépair** — En WebAssembly ou JS pur (libsodium.js ou crypto SubtleCrypto)
- **Drag & drop** — Glisser-déposer fichiers à chiffrer/déchiffrer
- **UI** — Glassmorphism dark theme, style JARVIS
- **Stockage clé** — LocalStorage (session), option export/import PEM

### Algorithmes Web
- Kyber-768 via `libsodium.js` (WASM) ou implémentation pure JS
- AES-256-GCM via Web Crypto API (`crypto.subtle`)

---

## 7. Desktop App (Future v3)

- **Tauri** (Rust backend) ou **Electron**
- Wrappé autour du CLI + web app
- UI native avec les mêmes fonctionnalités

---

## 8. Roadmap

### v1 (Actuel) — Core Encryption
- [x] CLI Python fonctionnel
- [x] Bibliothèque Python
- [x] Web app (single HTML)
- [x] Format .orret
- [x] README

### v2 — Key Sharing & Teams
- [ ] Partage de clé sécurisé (re-encapsulation)
- [ ] Chiffrement multi-destinataire
- [ ] Key rotation
- [ ] SSH agent integration

### v3 — Desktop GUI
- [ ] Application Tauri/Electron
- [ ] GUI native (drag-drop, progress bar)
- [ ] System tray
- [ ] Intégration cloud (Dropbox, Google Drive)

### v4 — Mobile
- [ ] App iOS (Swift)
- [ ] App Android (Kotlin)

### v5 — Plugins
- [ ] VS Code extension
- [ ] Browser extension
- [ ] vim/neovim plugin

---

## 9. Comparaison avec Outils Existants

| Outil | PQC | Facilité | Format | Notes |
|-------|-----|---------|--------|-------|
| **OrretCrypt** | ✅ Kyber-768 | ⭐⭐⭐ | .orret | Multi-format, web inclus |
| age | ❌ | ⭐⭐⭐⭐ | .age | Excellente UX mais pas PQC |
| gocryptfs | ❌ | ⭐⭐ | FUSE | Filesystem encryption |
| Cryptomator | ❌ | ⭐⭐⭐⭐ | vault | Cloud-focused |

---

## 10. Sécurité & Limitations

### Actuel
- ✅ IND-CCA2 secure (hybrid encryption)
- ✅ Authenticated encryption (AES-GCM)
- ✅ CSPRNG pour aléa
- ⚠️ Stockage clé: responsabilité utilisateur (pas de passphrase dans v1)

### Futures versions
- [ ] Passphrase pour protéger les clés privées (Argon2id + AES-256-GCM)
- [ ] Validation de clé (fingerprint)
- [ ] Audit de sécurité tiers
