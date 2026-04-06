# .loop — Native LLM Dataset Format

> *Les autres formats stockent des données. .loop stocke de l'intelligence.*

[![Version](https://img.shields.io/badge/format-v1.0-blue)]()
[![Python](https://img.shields.io/badge/python-3.10+-orange)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green)]()
[![unsafe: 0](https://img.shields.io/badge/unsafe-0-red)]()

---

## Le problème

Entraîner un LLM aujourd'hui, c'est jongler avec des formats qui n'ont jamais été conçus pour ça :

| Format | Problème réel |
|--------|---------------|
| `.jsonl` | Lent à parser. Pas de compression. Impossible de chercher au milieu. Aucun schema. |
| `.parquet` | Conçu pour de la data tabulaire. Pas pour des conversations multi-tours. |
| `.md` | Lisible par les humains. Illisible par les machines à l'entraînement. |
| HuggingFace datasets | Dépendance cloud. 2GB de RAM pour charger 100MB. |
| `.csv` | Conversation imbriquée en CSV. Sérieusement ? |

**La vraie douleur** : le *sequence packing*. Un context window de 2048 tokens coûte autant qu'un de 200 tokens sur GPU. Personne ne pense à ça au moment de construire le dataset. Résultat : 60–80% du GPU gaspillé sur du padding.

---

## La solution : `.loop`

Un format binaire columnar conçu spécifiquement pour le fine-tuning de LLMs :

- **Conversation-native** — `system/user/assistant` comme types de première classe, pas comme texte aplati
- **Sequence packing intégré** — pack automatique de plusieurs conversations courtes dans un seul context window, sans perte d'information
- **Streaming random-access** — index binaire embarqué, lit le batch 7000 sans lire les 6999 précédents
- **Qualité par record** — chaque exemple a un score. Filtre à la lecture sans réécrire le fichier
- **Self-describing** — métadonnées, version, tokenizer, stats : tout est dans le fichier
- **Compression Zstd par bloc** — ~70% plus petit que JSONL équivalent
- **Intégrité CRC64** — détecte la corruption sans charger le fichier entier
- **Local-first** — zéro dépendance cloud. Tourne sur un ThinkPad X250

---

## Quickstart

```python
from looplib import LoopWriter, LoopReader

# Écrire
writer = LoopWriter("coding_fr.loop", metadata={
    "name": "coding_fr_v1",
    "category": "code",
    "language": "fr",
    "source": "github + stackoverflow"
})

writer.add({
    "messages": [
        {"role": "system",    "content": "Tu es un expert Python."},
        {"role": "user",      "content": "Comment lire un fichier ligne par ligne ?"},
        {"role": "assistant", "content": "Utilise `with open(...) as f: for line in f:`"}
    ],
    "quality": 0.82,
    "tags": ["python", "io", "basics"]
})

writer.save()
# → coding_fr.loop (binaire, compressé, indexé)

# Lire — streaming, sans tout charger en RAM
reader = LoopReader("coding_fr.loop")
print(reader.info())

for record in reader.stream(min_quality=0.70, split="train"):
    messages = record["messages"]

# Sequence packing pour l'entraînement — la vraie innovation
for packed in reader.packed_sequences(max_len=2048, tokenizer=tokenizer):
    input_ids      = packed["input_ids"]       # [2048] — plein, pas de padding
    labels         = packed["labels"]           # [2048] — -100 sur les prompts
    attention_mask = packed["attention_mask"]   # [2048]
    # → GPU utilisé à ~95% au lieu de ~40%
```

---

## CLI

```bash
pip install looplib

# Inspecter
loop info coding_fr.loop

# Valider l'intégrité
loop validate coding_fr.loop

# Convertir depuis JSONL
loop convert dataset.jsonl --output coding_fr.loop --category code --lang fr

# Stats
loop stats coding_fr.loop --plot

# Filtrer et exporter
loop filter coding_fr.loop --min-quality 0.75 --output coding_fr_filtered.loop
```

---

## Format binaire (résumé)

```
┌─────────────────────────────────────────┐
│  HEADER          64 bytes               │
│  magic "LOOP" · version · flags · stats │
├─────────────────────────────────────────┤
│  INDEX           n_blocs × 24 bytes     │
│  offset · taille · n_records · split    │
├─────────────────────────────────────────┤
│  DATA BLOCS      variable               │
│  Zstd(records JSON) par bloc            │
├─────────────────────────────────────────┤
│  METADATA        Zstd(JSON)             │
│  nom · stats · schema · sources · tags  │
├─────────────────────────────────────────┤
│  FOOTER          16 bytes               │
│  CRC64 · magic "POOL"                   │
└─────────────────────────────────────────┘
```

Spec complète → [SPEC.md](./SPEC.md)

---

## Performances (benchmark sur X250 · i5-5300U)

| Format | Lecture 10K records | RAM pic | Taille (dataset 1GB) |
|--------|--------------------:|--------:|---------------------:|
| JSONL  | 4.2s               | 1.8 GB  | 1 000 MB             |
| Parquet| 1.1s               | 890 MB  | 380 MB               |
| **.loop** | **0.3s**        | **42 MB** | **290 MB**         |

*Lecture streaming par blocs de 512 records. RAM = pic mesuré avec tracemalloc.*

---

## Pourquoi pas HuggingFace datasets ?

HF datasets est excellent. .loop n'est pas un remplacement — c'est un complément.

HF est conçu pour le partage et la collaboration. .loop est conçu pour **l'entraînement local**, sur du matériel modeste, avec un contrôle total sur le format et les données.

.loop peut s'exporter vers HF datasets en une ligne :
```python
reader.to_huggingface()  # → datasets.Dataset
```

---

## Écosystème SOE

.loop est le format natif de [SOE](https://github.com/lvs0) — un écosystème d'IA open source, local-first, francophone.

- **Ruche** — collecteur de données → `.loop`
- **looplib** — ce repo
- **Orret** — modèle entraîné sur des `.loop`

---

## Contribuer

Issues et PRs bienvenues. La critique technique honnête est préférée à l'encouragement.

Construit par Lévy, 14 ans, France. Sur un ThinkPad X250. Sans demander la permission.

*"Un format de données, c'est une philosophie encodée en binaire."*
