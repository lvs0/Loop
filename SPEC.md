# SPEC.md — Spécification Technique .loop v1.0

> Version : 1.0  
> Statut : Draft  
> Auteur : Lévy (SOE Project)

---

## 1. Objectifs de design

| Objectif | Contrainte concrète |
|----------|---------------------|
| Streaming sans chargement complet | Index binaire → seek direct vers bloc N |
| Empreinte RAM minimale | Lecture par blocs de 512 records max |
| Compression efficace | Zstd niveau 9, par bloc |
| Conversation-native | `messages[]` avec roles comme types, pas du texte aplati |
| Sequence packing | Plusieurs conversations → 1 séquence d'entraînement pleine |
| Intégrité garantie | CRC64 sur tous les blocs de données |
| Self-describing | Métadonnées embedées, version pinée |
| Zéro dépendance système | Pure Python + zstandard + numpy |

---

## 2. Structure du fichier

```
Offset 0
┌──────────────────────────────────────────────────────────────┐
│  HEADER  (64 bytes, fixe)                                    │
├──────────────────────────────────────────────────────────────┤
│  INDEX   (n_blocs × 24 bytes)                                │
│  → démarre à offset 64                                       │
├──────────────────────────────────────────────────────────────┤
│  BLOC 0  (variable, Zstd)                                    │
│  BLOC 1                                                      │
│  ...                                                         │
│  BLOC N                                                      │
├──────────────────────────────────────────────────────────────┤
│  METADATA  (Zstd(JSON), variable)                            │
├──────────────────────────────────────────────────────────────┤
│  FOOTER  (16 bytes, fixe)                                    │
└──────────────────────────────────────────────────────────────┘
EOF
```

---

## 3. Header (64 bytes)

```
Offset  Taille  Type      Nom                  Description
──────  ──────  ────────  ───────────────────  ──────────────────────────────────
0       4       bytes     MAGIC                "LOOP" en ASCII (0x4C4F4F50)
4       2       uint16-LE VERSION_MAJOR         Actuellement 1
6       2       uint16-LE VERSION_MINOR         Actuellement 0
8       2       uint16-LE FLAGS                 Voir section 3.1
10      2       uint16-LE BLOCK_SIZE            Records par bloc (défaut : 512)
12      8       uint64-LE N_RECORDS             Nombre total de records
20      8       uint64-LE N_BLOCKS              Nombre de blocs
28      8       uint64-LE METADATA_OFFSET       Offset absolu vers METADATA
36      8       uint64-LE CREATED_AT            Unix timestamp (secondes)
44      4       uint32-LE SCHEMA_HASH           MD5[:4] du schéma JSON encodé
48      16      bytes     RESERVED              Zéros, usage futur
```

### 3.1 FLAGS (uint16, little-endian)

```
Bit  Signification
───  ─────────────────────────────────────
0    COMPRESSION_TYPE : 0=aucune, 1=Zstd
1    HAS_PRETOKENIZED : présence de tokens pré-calculés
2    HAS_QUALITY_INDEX : index de qualité séparé activé
3    MULTI_SPLIT : plusieurs splits dans le fichier
4-15 RESERVED (mettre à 0)
```

---

## 4. Index (n_blocs × 24 bytes)

Démarre immédiatement après le header (offset 64).

```
Par entrée (24 bytes) :
Offset  Taille  Type      Nom
──────  ──────  ────────  ────────────────────────────────────────
0       8       uint64-LE BLOCK_OFFSET       Offset absolu du bloc dans le fichier
8       4       uint32-LE COMPRESSED_SIZE    Taille compressée en bytes
12      4       uint32-LE UNCOMPRESSED_SIZE  Taille décompressée en bytes
16      4       uint32-LE N_RECORDS          Nombre de records dans ce bloc
20      2       uint16-LE SPLIT_ID           0=train 1=val 2=test 3=all
22      2       uint16-LE RESERVED
```

L'index permet le **random access** : pour lire le bloc K, seek à `INDEX[K].BLOCK_OFFSET` sans lire les K-1 blocs précédents.

---

## 5. Blocs de données

Chaque bloc est une séquence d'enregistrements sérialisés, compressée avec Zstd.

### 5.1 Structure interne du bloc (après décompression)

```
[BLOCK_MAGIC : 4 bytes "BLOK"]
[BLOCK_INDEX : 4 bytes uint32-LE]

Pour chaque record :
  [RECORD_LEN : 4 bytes uint32-LE]   ← taille du record en bytes
  [RECORD_DATA : RECORD_LEN bytes]   ← JSON UTF-8
```

### 5.2 Schéma d'un record (JSON)

```json
{
  "messages": [
    {"role": "system",    "content": "string"},
    {"role": "user",      "content": "string"},
    {"role": "assistant", "content": "string"}
  ],
  "quality":  0.78,
  "source":   "github.com/...",
  "language": "fr",
  "tags":     ["python", "async"],
  "tokens":   342,
  "split":    "train"
}
```

**Champs obligatoires :** `messages`  
**Champs optionnels :** tous les autres

**Roles valides :** `system`, `user`, `assistant`, `tool`, `function`

**Invariant :** Un record doit contenir au moins un message `user` et un message `assistant`.

### 5.3 Validation d'un record

```
✓ messages est une liste non vide
✓ Chaque message a "role" (string) et "content" (string non vide)
✓ role est dans {"system", "user", "assistant", "tool", "function"}
✓ Au moins 1 message user et 1 message assistant
✓ quality ∈ [0.0, 1.0] si présent
✓ language est un code ISO 639-1 à 2 lettres si présent
✓ tokens > 0 si présent
```

---

## 6. Métadonnées (Zstd(JSON))

Démarre à `METADATA_OFFSET` (indiqué dans le header).

```json
{
  "loop_format_version": "1.0",
  "name": "coding_fr_v1",
  "description": "Code Python/Bash collecté depuis GitHub et dev.to",
  "category": "code",
  "language": "fr",
  "version": "1.0",
  "created_at": "2026-04-06T14:32:00Z",
  "created_by": "Ruche/SOE",
  "n_records": 12543,
  "n_blocks": 25,
  "total_tokens_approx": 5312845,
  "avg_tokens_per_record": 423,
  "quality_stats": {
    "mean": 0.73,
    "min": 0.65,
    "max": 0.98,
    "p25": 0.68,
    "p75": 0.81
  },
  "splits": {
    "train": 11000,
    "val": 1000,
    "test": 543
  },
  "sources": ["github.com", "dev.to", "stackoverflow.com"],
  "tags": ["python", "bash", "linux", "async", "api"],
  "schema": {
    "roles": ["system", "user", "assistant"],
    "required_fields": ["messages"],
    "optional_fields": ["quality", "source", "language", "tags", "tokens", "split"]
  },
  "compression": "zstd",
  "block_size": 512
}
```

---

## 7. Footer (16 bytes)

Derniers 16 bytes du fichier.

```
Offset  Taille  Type      Nom
──────  ──────  ────────  ──────────────────────────────────────────
0       4       uint32-LE METADATA_COMPRESSED_SIZE  Taille des métadonnées compressées
4       8       uint64-LE CRC64                     CRC64/ECMA-182 de tous les blocs concaténés (décompressés)
12      4       bytes     MAGIC_END                 "POOL" (LOOP inversé, 0x504F4F4C)
```

**Validation du fichier** : 
1. Vérifier `MAGIC == "LOOP"` (offset 0)
2. Vérifier `MAGIC_END == "POOL"` (offset -4)
3. Calculer CRC64 de tous les blocs décompressés → comparer avec footer CRC64

---

## 8. Sequence Packing (algorithme)

C'est la fonctionnalité principale qui différencie .loop des autres formats.

### Problème

Un dataset de conversations courtes (100–300 tokens) entraîné avec `max_seq_len=2048` utilise ~10–15% du context window. Le reste est du padding. GPU payé, non utilisé.

### Solution

Pack plusieurs conversations dans une seule séquence d'entraînement, séparées par `EOS`. Le masque d'attention empêche les conversations de "se voir" mutuellement.

### Algorithme (Greedy First-Fit)

```python
def pack(records, tokenizer, max_len):
    """
    Greedy packing : remplit chaque séquence au maximum avant d'en ouvrir une nouvelle.
    Garantit : aucune perte d'information, aucun croisement de contexte entre convos.
    """
    current_ids     = []
    current_labels  = []
    current_pos_ids = []

    for record in records:
        tokens = tokenize_conversation(record, tokenizer)
        ids    = tokens["input_ids"]      # inclut EOS final
        labels = tokens["labels"]         # -100 sur system+user, ids sur assistant

        if len(current_ids) + len(ids) > max_len:
            if current_ids:
                yield pad_to(current_ids, current_labels, current_pos_ids, max_len)
            current_ids, current_labels, current_pos_ids = [], [], []

        # Position IDs : repartent de 0 à chaque nouvelle conversation
        pos_start = len(current_ids)
        current_pos_ids += list(range(len(ids)))  # 0..N pour cette convo
        current_ids    += ids
        current_labels += labels

    if current_ids:
        yield pad_to(current_ids, current_labels, current_pos_ids, max_len)
```

### Exemple visuel

```
Séquence naïve (2048 tokens) :
┌──────────────────────────────────────────────────────────────┐
│ CONVO A (342 tok) │               PADDING (1706 tok)         │
└──────────────────────────────────────────────────────────────┘
GPU utilisé : 16.7%

Séquence packée .loop (2048 tokens) :
┌────────────────────────────────────────────────────────────────┐
│ CONVO A │ EOS │ CONVO B │ EOS │ CONVO C │ EOS │ CONVO D │ PAD │
│ 342 tok │  1  │ 518 tok │  1  │ 623 tok │  1  │ 557 tok │  5  │
└────────────────────────────────────────────────────────────────┘
GPU utilisé : 99.8%
```

---

## 9. Format .looppatch (différentiel)

Un `.looppatch` permet d'ajouter des données à un `.loop` existant sans le réécrire.

```
HEADER : 32 bytes
  [4]  magic "PTCH"
  [8]  source_crc64     (CRC64 du .loop source attendu)
  [8]  created_at       (timestamp)
  [12] reserved

BLOCS ADDITIONNELS : même format que les blocs normaux

FOOTER : 8 bytes
  [4]  n_new_records
  [4]  magic "HCTP"
```

Application : `loop patch base.loop update.looppatch --output merged.loop`

---

## 10. Compatibilité et migration

### Depuis JSONL

```python
# Chaque ligne JSON doit avoir "messages" ou être convertie
loop convert data.jsonl --output data.loop

# Avec mapping de champs personnalisé
loop convert data.jsonl \
  --field-map "text=messages[0].content" \
  --default-role user
```

### Vers HuggingFace datasets

```python
reader = LoopReader("data.loop")
hf_dataset = reader.to_huggingface()
# → datasets.Dataset compatible avec Trainer
```

### Vers JSONL

```python
reader.to_jsonl("data.jsonl", min_quality=0.70)
```

---

## 11. Versioning et compatibilité

- **v1.x** : rétrocompatible. Un lecteur v1.3 lit un fichier v1.0.
- **v2.0** : breaking change potentiel. Header MAGIC change en "LOO2".
- Le `SCHEMA_HASH` dans le header permet de détecter un schéma incompatible avant de lire le fichier.

---

## 12. Sécurité

- .loop ne contient pas de code exécutable
- Les métadonnées JSON sont parsées avec `json.loads` standard (pas `eval`)
- La taille maximale d'un record est limitée à `MAX_RECORD_SIZE = 1_048_576` bytes (1MB) pour prévenir les attaques de décompression
- CRC64 protège contre la corruption silencieuse, pas contre la modification intentionnelle (pas de signature cryptographique dans la v1.0)

---

## 13. Implémentation de référence

→ `looplib/` dans ce repo (Python 3.10+)

Dépendances minimales :
```
zstandard>=0.21
numpy>=1.24
```

Dépendances optionnelles :
```
transformers  # pour sequence packing avec tokenizer HF
datasets      # pour export to_huggingface()
rich          # pour affichage CLI amélioré
```

---

*SOE Project — Lévy, France, 2026*  
*"Un format de données, c'est une philosophie encodée en binaire."*
