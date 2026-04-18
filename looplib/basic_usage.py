"""
examples/basic_usage.py — Démonstration complète de looplib

Lance avec : python examples/basic_usage.py
"""

import sys
import tempfile
from pathlib import Path

# Ajouter le parent au path si looplib n'est pas installé
sys.path.insert(0, str(Path(__file__).parent.parent))

from looplib import LoopWriter, LoopReader


def demo_write_and_read():
    """Exemple 1 : écrire puis lire un fichier .loop."""
    print("\n" + "─" * 50)
    print("  EXEMPLE 1 : Écriture + Lecture")
    print("─" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "demo.loop"

        # ── Écriture ──────────────────────────────────────────────────────────
        writer = LoopWriter(path, metadata={
            "name":        "demo_coding_fr",
            "category":    "code",
            "language":    "fr",
            "description": "Dataset de démonstration looplib",
        })

        conversations = [
            {
                "messages": [
                    {"role": "system",    "content": "Tu es un expert Python. Réponds en français."},
                    {"role": "user",      "content": "Comment lire un fichier CSV ligne par ligne ?"},
                    {"role": "assistant", "content":
                        "Utilise `csv.reader` ou `pandas.read_csv()` :\n\n"
                        "```python\nimport csv\nwith open('data.csv') as f:\n"
                        "    reader = csv.reader(f)\n    for row in reader:\n        print(row)\n```"
                    },
                ],
                "quality":  0.88,
                "language": "fr",
                "tags":     ["python", "csv", "io"],
                "tokens":   87,
                "split":    "train",
            },
            {
                "messages": [
                    {"role": "user",      "content": "C'est quoi la différence entre list et tuple en Python ?"},
                    {"role": "assistant", "content":
                        "**list** : mutable, modifiable après création.\n"
                        "**tuple** : immutable, plus rapide, utilisé pour des données fixes.\n\n"
                        "```python\nma_liste  = [1, 2, 3]   # modifiable\nmon_tuple = (1, 2, 3)   # fixe\n```"
                    },
                ],
                "quality":  0.76,
                "language": "fr",
                "tags":     ["python", "types", "basics"],
                "tokens":   62,
                "split":    "train",
            },
            {
                "messages": [
                    {"role": "user",      "content": "Comment créer un environnement virtuel Python ?"},
                    {"role": "assistant", "content":
                        "```bash\npython -m venv mon_env\nsource mon_env/bin/activate  # Linux/Mac\nmon_env\\Scripts\\activate      # Windows\npip install -r requirements.txt\n```"
                    },
                ],
                "quality":  0.71,
                "language": "fr",
                "tags":     ["python", "venv", "linux"],
                "tokens":   45,
                "split":    "val",
            },
        ]

        for conv in conversations:
            writer.add(conv)

        size = writer.save()
        print(f"\n  ✓ Fichier créé : {path.name}")
        print(f"  ✓ Taille       : {size / 1024:.2f} KB")
        print(f"  ✓ Records      : {len(conversations)}")

        # ── Lecture ───────────────────────────────────────────────────────────
        reader = LoopReader(path)
        info   = reader.info()

        print(f"\n  Métadonnées :")
        print(f"    Nom      : {info['name']}")
        print(f"    Langue   : {info['language']}")
        print(f"    Records  : {info['n_records']}")
        print(f"    Blocs    : {info['n_blocks']}")
        print(f"    Qualité  : {info['quality_stats']}")

        print(f"\n  Stream (min_quality=0.75, split=train) :")
        for i, record in enumerate(reader.stream(min_quality=0.75, split="train")):
            user_msg = next(m["content"] for m in record["messages"] if m["role"] == "user")
            print(f"    [{i}] Q: {user_msg[:60]}...")
            print(f"         qualité={record.get('quality')} | tokens={record.get('tokens')}")


def demo_convert_jsonl():
    """Exemple 2 : convertir depuis JSONL."""
    print("\n" + "─" * 50)
    print("  EXEMPLE 2 : Conversion depuis JSONL")
    print("─" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        # Créer un JSONL de test (format Alpaca)
        jsonl_path = Path(tmpdir) / "alpaca_sample.jsonl"
        import json

        alpaca_records = [
            {
                "instruction": "Explique ce qu'est une liste en compréhension Python.",
                "output": "Une list comprehension permet de créer une liste en une ligne : `[x**2 for x in range(10)]`",
                "quality": 0.80,
            },
            {
                "instruction": "Comment décompresser une archive .tar.gz sous Linux ?",
                "output": "Utilise la commande : `tar -xzf archive.tar.gz`\nL'option -x extrait, -z décompresse gzip, -f spécifie le fichier.",
                "quality": 0.85,
            },
        ]

        with open(jsonl_path, "w") as f:
            for r in alpaca_records:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

        print(f"\n  JSONL source : {len(alpaca_records)} records")

        # Convertir via LoopWriter + normalisation manuelle
        loop_path = Path(tmpdir) / "converted.loop"
        writer    = LoopWriter(loop_path, metadata={
            "name":     "alpaca_fr_sample",
            "category": "instruct",
            "language": "fr",
            "source":   "alpaca",
        })

        with open(jsonl_path) as f:
            for line in f:
                record = json.loads(line)
                # Normaliser Alpaca → format .loop
                writer.add({
                    "messages": [
                        {"role": "user",      "content": record["instruction"]},
                        {"role": "assistant", "content": record["output"]},
                    ],
                    "quality": record.get("quality"),
                    "split":   "train",
                })

        size = writer.save()
        print(f"  .loop créé  : {size / 1024:.2f} KB")

        # Vérification
        reader = LoopReader(loop_path)
        print(f"  Records lus : {reader.count()}")


def demo_stats():
    """Exemple 3 : statistiques et filtrage."""
    print("\n" + "─" * 50)
    print("  EXEMPLE 3 : Statistiques + Filtrage")
    print("─" * 50)

    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "stats_demo.loop"

        writer = LoopWriter(path, block_size=10)
        import random
        random.seed(42)

        for i in range(100):
            writer.add({
                "messages": [
                    {"role": "user",      "content": f"Question {i}"},
                    {"role": "assistant", "content": f"Réponse {i}"},
                ],
                "quality": round(random.uniform(0.5, 1.0), 2),
                "split":   "train" if i < 80 else "val",
                "tokens":  random.randint(20, 200),
            })
        writer.save()

        reader = LoopReader(path)

        total      = reader.count()
        high_q     = reader.count(min_quality=0.85)
        train_only = reader.count(split="train")
        val_only   = reader.count(split="val")

        print(f"\n  Total records   : {total}")
        print(f"  Qualité ≥ 0.85  : {high_q} ({100*high_q//total}%)")
        print(f"  Split train     : {train_only}")
        print(f"  Split val       : {val_only}")

        # Exporter un sous-ensemble filtré
        filtered_path = Path(tmpdir) / "high_quality.loop"
        fw = LoopWriter(filtered_path, metadata={"name": "high_quality_subset"})
        fw.add_many(list(reader.stream(min_quality=0.85, split="train")))
        fw.save()

        filtered_reader = LoopReader(filtered_path)
        print(f"\n  Sous-ensemble filtré (q≥0.85 + train) : {filtered_reader.count()} records")


if __name__ == "__main__":
    print("\n  looplib — Démonstration complète")
    print("  Format .loop v1.0 · SOE Project")

    demo_write_and_read()
    demo_convert_jsonl()
    demo_stats()

    print("\n  ✓ Toutes les démonstrations réussies.\n")
