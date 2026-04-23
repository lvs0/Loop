"""
loop CLI — Interface ligne de commande pour le format .loop

Commandes :
  loop info    <fichier.loop>          Inspecter un fichier
  loop validate <fichier.loop>         Vérifier l'intégrité
  loop convert  <input> [options]      Convertir depuis JSONL
  loop stats    <fichier.loop>         Statistiques détaillées
  loop filter   <fichier.loop>         Filtrer et exporter

Usage :
  pip install looplib
  loop info coding_fr.loop
"""

from __future__ import annotations

import sys
import json
import time
import struct
import logging
import argparse
from pathlib import Path
from typing import Optional, List, Dict, Any, Iterator

from looplib import __version__, __format_version__

try:
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
    from rich.console import Console
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

logging.basicConfig(format="[loop] %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


def _progress_context(desc: str, total: Optional[int] = None):
    """Context manager for progress display (rich if available, else silent)."""
    if RICH_AVAILABLE and total:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console,
        )
    elif RICH_AVAILABLE:
        return Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        )
    else:
        # Dummy context manager when rich is not available
        class DummyProgress:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                pass
            def add_task(self, *args, **kwargs):
                return 0
            def update(self, *args, **kwargs):
                pass
        return DummyProgress()


def cmd_info(args) -> None:
    """Affiche les informations d'un fichier .loop."""
    from looplib.reader import LoopReader
    reader = LoopReader(args.file)
    info   = reader.info()

    print(f"\n{'─' * 50}")
    print(f"  {args.file}")
    print(f"{'─' * 50}")
    print(f"  Format         : .loop v{info['format_version']}")
    print(f"  Nom            : {info['name']}")
    print(f"  Catégorie      : {info['category']}")
    print(f"  Langue         : {info['language']}")
    print(f"  Taille         : {info['file_size_mb']} MB")
    print(f"  Records        : {info['n_records']:,}")
    print(f"  Blocs          : {info['n_blocks']}")
    print(f"  Compression    : {info['compression']}")
    print(f"  Créé le        : {info['created_at']}")

    if info["splits"]:
        print(f"\n  Splits :")
        for split, count in info["splits"].items():
            if count > 0:
                print(f"    {split:8s} : {count:,}")

    if info["quality_stats"]:
        qs = info["quality_stats"]
        print(f"\n  Qualité :")
        print(f"    moyenne  : {qs.get('mean', '?')}")
        print(f"    min/max  : {qs.get('min', '?')} / {qs.get('max', '?')}")
        print(f"    p25/p75  : {qs.get('p25', '?')} / {qs.get('p75', '?')}")

    if info["total_tokens"]:
        print(f"\n  Tokens approx  : {info['total_tokens']:,}")

    if info["sources"]:
        print(f"\n  Sources        : {', '.join(info['sources'][:5])}")

    if info["tags"]:
        print(f"  Tags           : {', '.join(info['tags'][:10])}")

    print(f"{'─' * 50}\n")


def cmd_validate(args) -> None:
    """Vérifie l'intégrité d'un fichier .loop."""
    from looplib.reader import LoopReader, LoopParseError
    from looplib.constants import MAGIC_HEADER, MAGIC_FOOTER, FOOTER_SIZE

    path = Path(args.file)
    print(f"\nValidation : {path}")

    errors   = []
    warnings = []

    # 1. Vérifier magic bytes
    try:
        with open(path, "rb") as f:
            header_magic = f.read(4)
            f.seek(-4, 2)
            footer_magic = f.read(4)

        if header_magic != MAGIC_HEADER:
            errors.append(f"Magic header invalide : {header_magic!r}")
        else:
            print("  ✓ Magic header OK")

        if footer_magic != MAGIC_FOOTER:
            errors.append(f"Magic footer invalide : {footer_magic!r}")
        else:
            print("  ✓ Magic footer OK")
    except Exception as e:
        errors.append(f"Impossible de lire le fichier : {e}")

    # 2. Parser header + index
    try:
        reader = LoopReader(path)
        print(f"  ✓ Header/Index parsé ({reader._header['n_records']:,} records, {reader._header['n_blocks']} blocs)")
    except LoopParseError as e:
        errors.append(f"Header/Index invalide : {e}")
        _print_result(errors, warnings)
        return

    # 3. Lecture de tous les blocs avec progress
    total_records = 0
    n_blocks = reader._header["n_blocks"]
    start = time.time()
    
    with _progress_context("Validation des blocs", total=n_blocks) as progress:
        task = progress.add_task("Validation", total=n_blocks)
        try:
            for block_idx in range(n_blocks):
                records = reader.read_block(block_idx)
                total_records += len(records)
                progress.update(task, advance=1)
            elapsed = time.time() - start
            print(f"  ✓ Tous les blocs lus ({total_records:,} records en {elapsed:.2f}s)")
        except Exception as e:
            errors.append(f"Erreur de lecture des blocs : {e}")

    # 4. Cohérence count
    declared  = reader._header["n_records"]
    if total_records != declared:
        warnings.append(
            f"Incohérence : header déclare {declared} records, {total_records} lus"
        )

    # 5. Métadonnées
    try:
        meta = reader.metadata
        print(f"  ✓ Métadonnées OK (format v{meta.get('loop_format_version', '?')})")
    except Exception as e:
        warnings.append(f"Métadonnées illisibles : {e}")

    _print_result(errors, warnings)


def _print_result(errors, warnings) -> None:
    if warnings:
        for w in warnings:
            print(f"  ⚠ {w}")
    if errors:
        for e in errors:
            print(f"  ✗ {e}")
        print("\n  RÉSULTAT : INVALIDE\n")
        sys.exit(1)
    else:
        print("\n  RÉSULTAT : VALIDE ✓\n")


def cmd_convert(args) -> None:
    """Convertit un fichier JSONL vers .loop."""
    from looplib.writer import LoopWriter
    from looplib.validator import ValidationError

    input_path  = Path(args.input)
    output_path = Path(args.output) if args.output else input_path.with_suffix(".loop")

    if not input_path.exists():
        print(f"Fichier introuvable : {input_path}")
        sys.exit(1)

    # Count total lines for progress bar
    total_lines = sum(1 for _ in open(input_path, "r", encoding="utf-8"))

    metadata = {
        "name":     args.name or input_path.stem,
        "category": args.category or "general",
        "language": args.lang or "fr",
        "source":   str(input_path),
    }

    writer  = LoopWriter(output_path, metadata=metadata)
    count   = 0
    skipped = 0

    print(f"Conversion : {input_path} → {output_path}")

    with _progress_context("Conversion", total=total_lines) as progress:
        task = progress.add_task("Conversion", total=total_lines)
        with open(input_path, "r", encoding="utf-8") as f:
            for lineno, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    progress.update(task, advance=1)
                    continue
                try:
                    record = json.loads(line)
                    # Normaliser si le format est "instruction/output" plutôt que "messages"
                    if "messages" not in record:
                        record = _normalize_record(record)
                    writer.add(record)
                    count += 1
                except (json.JSONDecodeError, ValidationError) as e:
                    logger.debug(f"Ligne {lineno} ignorée : {e}")
                    skipped += 1
                progress.update(task, advance=1)

    size = writer.save()
    print(f"  ✓ {count:,} records convertis ({skipped} ignorés)")
    print(f"  ✓ Fichier : {output_path} ({size / 1024:.1f} KB)\n")


def _normalize_record(record: dict) -> dict:
    """Essaie de convertir différents formats courants vers le format .loop."""
    # Format Alpaca : instruction + output
    if "instruction" in record and "output" in record:
        messages = []
        if record.get("system"):
            messages.append({"role": "system", "content": record["system"]})
        messages.append({"role": "user",      "content": record["instruction"]})
        messages.append({"role": "assistant", "content": record["output"]})
        return {
            "messages": messages,
            "quality":  record.get("quality"),
            "source":   record.get("source"),
        }
    # Format simple : prompt + response
    if "prompt" in record and "response" in record:
        return {
            "messages": [
                {"role": "user",      "content": record["prompt"]},
                {"role": "assistant", "content": record["response"]},
            ]
        }
    raise ValueError(f"Format non reconnu, champs disponibles : {list(record.keys())}")


def _ascii_bar(value: int, max_value: int, width: int = 30) -> str:
    """Génère une barre ASCII proportionnelle."""
    if max_value == 0:
        return " " * width
    bar_len = int(value * width / max_value)
    return "█" * bar_len + "░" * (width - bar_len)


def _quality_histogram(quality_buckets: dict, total: int) -> str:
    """Génère un histogramme ASCII vertical de la distribution de qualité."""
    if not quality_buckets or total == 0:
        return "  (aucune donnée)"

    lines   = []
    buckets = list(quality_buckets.items())
    max_val = max(v for _, v in buckets)

    lines.append("")
    lines.append("  Distribution qualité — histogramme ASCII")
    lines.append("  ──────────────────────────────────────────")

    rows  = 16
    scale = max_val / rows if max_val > 0 else 1

    for row in range(rows, 0, -1):
        threshold = row * scale
        line = "  "
        for bucket, count in buckets:
            bar_char = "█" if count >= threshold else " "
            line += f" {bar_char}"
        lines.append(line)

    label_line   = "  └" + "┴─" * len(buckets)
    bucket_labels = "  " + " ".join(f"{b.split('-')[0]}" for b, _ in buckets)
    lines.append(label_line)
    lines.append(bucket_labels)

    return "\n".join(lines)


def cmd_stats(args) -> None:
    """Affiche des statistiques détaillées."""
    from looplib.reader import LoopReader

    reader = LoopReader(args.file)
    info   = reader.info()

    max_len = getattr(args, "max_len", 2048)

    print(f"\nStatistiques : {args.file}")
    print(f"{'─' * 40}")

    # Distribution des qualités
    quality_buckets = {f"{i/10:.1f}-{(i+1)/10:.1f}": 0 for i in range(10)}
    total = 0
    tokens_total = 0
    tags_count   = {}
    lang_count   = {}
    split_count  = {"train": 0, "val": 0, "test": 0}

    for record in reader.stream(min_quality=args.min_quality, split=args.split, language=args.language):
        q = record.get("quality")
        if q is not None:
            bucket_idx = min(int(float(q) * 10), 9)
            key = list(quality_buckets.keys())[bucket_idx]
            quality_buckets[key] += 1

        tokens = record.get("tokens")
        if tokens:
            tokens_total += tokens

        tags = record.get("tags", [])
        for tag in tags:
            tags_count[tag] = tags_count.get(tag, 0) + 1

        lang = record.get("language")
        if lang:
            lang_count[lang] = lang_count.get(lang, 0) + 1

        split = record.get("split", "train")
        if split in split_count:
            split_count[split] += 1

        total += 1

    # ── Qualité ──────────────────────────────────────────────────────────────
    max_bucket = max(quality_buckets.values(), default=0)
    print(f"\n  Distribution qualité ({total:,} records) :")
    if max_bucket == 0:
        print("    (aucune donnée de qualité disponible)")
    else:
        if args.plot:
            print(_quality_histogram(quality_buckets, total))
        for bucket, count in quality_buckets.items():
            bar = _ascii_bar(count, max_bucket)
            pct = count / total * 100 if total else 0
            print(f"    {bucket} │ {bar} │ {count:,} ({pct:.1f}%)")

    # ── Tokens ─────────────────────────────────────────────────────────────────
    if tokens_total > 0:
        avg_tokens = tokens_total / total
        print(f"\n  Tokens :")
        print(f"    Total     : {tokens_total:,}")
        print(f"    Moyenne   : {avg_tokens:.0f} / record")

    # ── Langues ───────────────────────────────────────────────────────────────
    if lang_count:
        print(f"\n  Langues ({len(lang_count)} categories) :")
        sorted_langs = sorted(lang_count.items(), key=lambda x: -x[1])[:8]
        max_lang = max(lang_count.values(), default=1)
        for lang, count in sorted_langs:
            bar = _ascii_bar(count, max_lang, 20)
            pct = count / total * 100
            print(f"    {lang:>6} │ {bar} {pct:5.1f}%")

    # ── Tags ──────────────────────────────────────────────────────────────────
    if tags_count:
        print(f"\n  Top tags ({len(tags_count)} total) :")
        sorted_tags = sorted(tags_count.items(), key=lambda x: -x[1])[:10]
        max_tag = max(tags_count.values(), default=1)
        for tag, count in sorted_tags:
            bar = _ascii_bar(count, max_tag, 20)
            pct = count / total * 100
            print(f"    {tag:<15} │ {bar} {pct:5.1f}%")

    # ── Splits ────────────────────────────────────────────────────────────────
    if any(v > 0 for v in split_count.values()):
        print(f"\n  Splits :")
        max_split = max(split_count.values(), default=1)
        for split, count in split_count.items():
            bar = _ascii_bar(count, max_split, 20)
            pct = count / total * 100 if total else 0
            print(f"    {split:<6} │ {bar} {count:,} ({pct:.1f}%)")

    # ── Efficiency estimate ──────────────────────────────────────────────────
    if tokens_total > 0 and info.get("block_size"):
        naive_seqs  = total
        packed_seqs = tokens_total / max_len
        if packed_seqs > 0:
            speedup = naive_seqs / packed_seqs
            naive_util   = (tokens_total / naive_seqs) / max_len * 100
            packed_util  = min(99.5, (tokens_total / packed_seqs) / max_len * 100)
            print(f"\n  Efficiency estimate (max_seq_len={max_len}) :")
            print(f"    Naive  GPU util : ~{naive_util:.1f}%  ({naive_seqs:,} sequences)")
            print(f"    Packed GPU util : ~{packed_util:.1f}%  ({packed_seqs:.0f} sequences)")
            print(f"    Speedup         : {speedup:.1f}x fewer sequences")

    print()


def cmd_pack(args) -> None:
    """
    Pack records into training sequences and display efficiency stats.

    Requires a HuggingFace tokenizer name (e.g. meta-llama/Llama-3.2-1B, gpt2).
    Uses SequencePacker to pack multiple short conversations into full GPU sequences.
    """
    from looplib.reader import LoopReader
    from looplib.packer import SequencePacker
    import transformers

    reader = LoopReader(args.file)

    # Load tokenizer
    print(f"\nChargement du tokenizer : {args.tokenizer}")
    try:
        tok = transformers.AutoTokenizer.from_pretrained(args.tokenizer, use_fast=False)
    except Exception as e:
        print(f"Erreur de chargement du tokenizer : {e}")
        sys.exit(1)

    if not hasattr(tok, "apply_chat_template"):
        print(f"Attention : le tokenizer n'a pas de apply_chat_template — packing en mode texte brut.")

    max_len     = args.max_seq_len
    min_quality = getattr(args, "min_quality", None)
    split       = getattr(args, "split", None)

    # Efficiency estimate via SequencePacker
    print("\nAnalyse de l'efficacité du packing...")
    packer = SequencePacker(tok, max_seq_len=max_len)

    try:
        eff = packer.efficiency(reader.stream(min_quality=min_quality, split=split))
    except Exception as e:
        print(f"Erreur lors de l'analyse : {e}")
        sys.exit(1)

    if not eff:
        print("Aucun record à analyser.")
        sys.exit(0)

    print(f"\n{'─' * 50}")
    print(f"  Efficiency — {args.file}")
    print(f"  Tokenizer : {args.tokenizer}")
    print(f"  max_seq_len : {max_len}")
    print(f"{'─' * 50}")
    print(f"  Records analysés  : {eff['n_records']:,}")
    print(f"  Tokens moyen/rec  : {eff['avg_tokens']:,}")
    print(f"  GPU util (naive)   : {eff['naive_gpu_usage']:.1f}%   — 1 convo = 1 seq")
    print(f"  GPU util (packed)  : {eff['packed_gpu_usage']:.1f}%   — multi-convo / seq")
    print(f"  Sequences (naive)  : {eff['naive_sequences']:,}")
    print(f"  Sequences (packed) : {eff['packed_sequences']:.0f}")
    print(f"  Speedup            : {eff['speedup_factor']:.1f}x fewer sequences")
    print(f"{'─' * 50}")

    if args.output:
        count = 0
        print(f"\nExport vers {args.output}...")
        with open(args.output, "w") as f:
            for packed in reader.packed_sequences(tok, max_seq_len=max_len,
                                                   min_quality=min_quality, split=split):
                f.write(json.dumps({
                    "input_ids":      packed["input_ids"],
                    "labels":         packed["labels"],
                    "attention_mask": packed["attention_mask"],
                    "position_ids":  packed["position_ids"],
                }) + "\n")
                count += 1
                if args.limit and count >= args.limit:
                    break
        print(f"  ✓ {count:,} séquences exportées")
    else:
        print(f"\n  (utilisez --output pour exporter les séquences)")

    print()


def cmd_filter(args) -> None:
    """Filtre un .loop et crée un nouveau fichier."""
    from looplib.reader import LoopReader
    from looplib.writer import LoopWriter

    reader = LoopReader(args.file)
    meta   = dict(reader.metadata)
    meta["name"]   = meta.get("name", "") + "_filtered"
    meta["source"] = str(args.file)

    output = args.output or Path(args.file).stem + "_filtered.loop"
    writer = LoopWriter(output, metadata=meta)
    count  = 0

    for record in reader.stream(min_quality=args.min_quality, split=args.split):
        writer.add(record)
        count += 1

    if count == 0:
        print("Aucun record ne correspond aux filtres.")
        return

    size = writer.save()
    print(f"✓ {count:,} records → {output} ({size / 1024:.1f} KB)")


def cmd_count(args) -> None:
    """Compte les records correspondant aux filtres."""
    from looplib.reader import LoopReader

    reader = LoopReader(args.file)
    count  = reader.count(min_quality=args.min_quality, split=args.split)
    total  = reader._header["n_records"]

    print(f"{count:,} records", end="")
    if args.min_quality is not None or args.split is not None:
        print(f" (sur {total:,} total)", end="")
    print()


def cmd_merge(args) -> None:
    """Fusionne plusieurs fichiers .loop en un seul."""
    from looplib.reader import LoopReader
    from looplib.writer import LoopWriter
    from looplib.validator import ValidationError

    input_paths = [Path(p) for p in args.files]
    output_path = Path(args.output)

    for p in input_paths:
        if not p.exists():
            print(f"Fichier introuvable : {p}")
            sys.exit(1)

    # Collect metadata from first file as base
    first_reader = LoopReader(input_paths[0])
    merged_meta  = dict(first_reader.metadata)
    merged_meta["name"]        = args.name or (merged_meta.get("name", "merged") + "_merged")
    merged_meta["description"]  = f"Fusion de {len(input_paths)} fichiers .loop"
    merged_meta["source"]      = ", ".join(str(p) for p in input_paths)

    writer   = LoopWriter(output_path, metadata=merged_meta)
    total    = 0
    skipped  = 0

    print(f"Fusion de {len(input_paths)} fichiers .loop → {output_path}")

    for p in input_paths:
        reader = LoopReader(p)
        file_total = 0
        for record in reader.stream():
            try:
                writer.add(record)
                file_total += 1
            except ValidationError:
                skipped += 1
        total += file_total
        print(f"  + {file_total:,} records depuis {p.name}")

    if total == 0:
        print("Aucun record à fusionner.")
        sys.exit(1)

    size = writer.save()
    print(f"\n  ✓ {total:,} records fusionnés ({skipped} ignorés)")
    print(f"  ✓ Fichier  : {output_path} ({size / 1024:.1f} KB)\n")


def cmd_inspect(args) -> None:
    """Inspecte un record spécifique ou un échantillon aléatoire."""
    from looplib.reader import LoopReader

    reader = LoopReader(args.file)
    info = reader.info()

    # Determine which record(s) to show
    if args.record is not None:
        # Specific record by index
        if args.record < 0 or args.record >= info["n_records"]:
            print(f"Index hors limites : {args.record} (max: {info['n_records'] - 1})")
            sys.exit(1)
        
        # Find which block contains this record
        block_idx = args.record // info["block_size"]
        offset_in_block = args.record % info["block_size"]
        
        records = reader.read_block(block_idx)
        if offset_in_block >= len(records):
            print(f"Record {args.record} non trouvé dans le bloc {block_idx}")
            sys.exit(1)
        
        records_to_show = [(args.record, records[offset_in_block])]
    else:
        # Sample random records
        import random
        sample_size = min(args.sample or 3, info["n_records"])
        indices = sorted(random.sample(range(info["n_records"]), sample_size))
        
        records_to_show = []
        for idx in indices:
            block_idx = idx // info["block_size"]
            offset_in_block = idx % info["block_size"]
            block_records = reader.read_block(block_idx)
            if offset_in_block < len(block_records):
                records_to_show.append((idx, block_records[offset_in_block]))

    # Display records
    print(f"\n{'─' * 60}")
    print(f"  Inspection : {args.file}")
    print(f"{'─' * 60}")
    
    for idx, record in records_to_show:
        print(f"\n  Record #{idx}")
        print(f"  {'─' * 56}")
        
        # Messages
        print(f"  Messages ({len(record.get('messages', []))}):")
        for i, msg in enumerate(record.get('messages', [])):
            role = msg.get('role', '?')
            content = msg.get('content', '')
            # Truncate long content
            if len(content) > 200 and not args.full:
                content = content[:200] + "... [truncated, use --full]"
            print(f"    [{role:10}] {content[:80]}{'...' if len(content) > 80 else ''}")
        
        # Metadata fields
        meta_fields = ['quality', 'language', 'split', 'source', 'tokens', 'tags']
        meta = {k: record.get(k) for k in meta_fields if k in record}
        if meta:
            print(f"\n  Métadonnées:")
            for k, v in meta.items():
                if k == 'tags' and isinstance(v, list):
                    v = ', '.join(v)
                print(f"    {k:12} : {v}")
    
    print(f"\n{'─' * 60}\n")


def cmd_patch_create(args) -> None:
    """Crée un fichier patch (.looppatch) à partir de nouveaux records."""
    from looplib.patcher import LoopPatcher, PatchError

    input_path = Path(args.records)
    if not input_path.exists():
        print(f"Fichier source introuvable : {input_path}")
        sys.exit(1)

    try:
        size = LoopPatcher.create(args.base, args.records, args.output)
        print(f"\n  ✓ Patch créé : {args.output}")
        print(f"  ✓ Taille     : {size / 1024:.1f} KB\n")
    except PatchError as e:
        print(f"\n  ✗ Erreur : {e}\n")
        sys.exit(1)


def cmd_patch_apply(args) -> None:
    """Applique un fichier patch (.looppatch) à un fichier .loop."""
    from looplib.patcher import LoopPatcher, PatchError

    try:
        size = LoopPatcher.apply(args.base, args.patch, args.output)
        print(f"\n  ✓ Patch appliqué : {args.output}")
        print(f"  ✓ Taille fusionnée : {size / 1024:.1f} KB\n")
    except PatchError as e:
        print(f"\n  ✗ Erreur : {e}\n")
        sys.exit(1)


def cmd_diff(args) -> None:
    """Compare deux fichiers .loop et affiche les différences."""
    from looplib.reader import LoopReader

    reader_a = LoopReader(args.file_a)
    reader_b = LoopReader(args.file_b)

    info_a = reader_a.info()
    info_b = reader_b.info()

    print(f"\n{'─' * 50}")
    print(f"  Diff : {args.file_a} vs {args.file_b}")
    print(f"{'─' * 50}")

    # Compare basic stats
    fields = [
        ("Records", "n_records", "{:,}"),
        ("Blocs", "n_blocks", "{}"),
        ("Taille (MB)", "file_size_mb", "{:.2f}"),
        ("Tokens", "total_tokens", "{:,}"),
    ]

    for label, key, fmt in fields:
        val_a = info_a.get(key, 0)
        val_b = info_b.get(key, 0)
        diff = val_b - val_a
        sign = "+" if diff > 0 else ""
        print(f"  {label:15} │ A: {fmt.format(val_a):>12} │ B: {fmt.format(val_b):>12} │ Δ: {sign}{diff:,}")

    # Compare quality stats
    qa = info_a.get("quality_stats", {})
    qb = info_b.get("quality_stats", {})
    if qa or qb:
        print(f"\n  Qualité :")
        for stat in ["mean", "min", "max"]:
            va = qa.get(stat, "-")
            vb = qb.get(stat, "-")
            print(f"    {stat:8} │ A: {va:>6} │ B: {vb:>6}")

    # Compare splits
    sa = info_a.get("splits", {})
    sb = info_b.get("splits", {})
    if sa or sb:
        print(f"\n  Splits :")
        for split in ["train", "val", "test"]:
            va = sa.get(split, 0)
            vb = sb.get(split, 0)
            diff = vb - va
            sign = "+" if diff > 0 else ""
            print(f"    {split:8} │ A: {va:>6,} │ B: {vb:>6,} │ Δ: {sign}{diff:,}")

    # Compare tags
    ta = set(info_a.get("tags", []))
    tb = set(info_b.get("tags", []))
    common = ta & tb
    only_a = ta - tb
    only_b = tb - ta

    if only_a or only_b:
        print(f"\n  Tags :")
        if only_a:
            print(f"    Uniquement A : {', '.join(sorted(only_a)[:10])}")
        if only_b:
            print(f"    Uniquement B : {', '.join(sorted(only_b)[:10])}")
        if common:
            print(f"    Communs      : {len(common)} tags")

    print(f"{'─' * 50}\n")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="loop",
        description="Outil CLI pour le format .loop",
    )
    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"loop {__version__} (format v{__format_version__[0]}.{__format_version__[1]})"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # loop info
    p_info = subparsers.add_parser("info", help="Inspecter un fichier .loop")
    p_info.add_argument("file", help="Chemin vers le fichier .loop")

    # loop validate
    p_val = subparsers.add_parser("validate", help="Vérifier l'intégrité d'un fichier .loop")
    p_val.add_argument("file")

    # loop convert
    p_conv = subparsers.add_parser("convert", help="Convertir JSONL → .loop")
    p_conv.add_argument("input",            help="Fichier source (.jsonl)")
    p_conv.add_argument("--output", "-o",   help="Fichier de sortie (.loop)")
    p_conv.add_argument("--name",           help="Nom du dataset")
    p_conv.add_argument("--category",       help="Catégorie (code, instruct, ...)")
    p_conv.add_argument("--lang",           help="Code langue (fr, en, ...)")

    # loop stats
    p_stats = subparsers.add_parser("stats", help="Statistiques détaillées")
    p_stats.add_argument("file")
    p_stats.add_argument("--plot", "-p", action="store_true", help="Afficher un histogramme ASCII de la distribution de qualité")
    p_stats.add_argument("--max-len", "-m", type=int, default=2048, help="Longueur max de séquence pour l'estimation d'efficacité (défaut: 2048)")

    # loop pack
    p_pack = subparsers.add_parser("pack", help="Pack records en séquences + stats d'efficacité")
    p_pack.add_argument("file",                       help="Fichier .loop source")
    p_pack.add_argument("--tokenizer", "-t", required=True, help="Nom du tokenizer HuggingFace (ex: gpt2, meta-llama/Llama-3.2-1B)")
    p_pack.add_argument("--max-seq-len", "-l", type=int, default=2048, help="Longueur max de séquence (défaut: 2048)")
    p_pack.add_argument("--min-quality", "-q", type=float, default=None, help="Score qualité minimum")
    p_pack.add_argument("--split", "-s", choices=["train", "val", "test"], help="Filtrer par split")
    p_pack.add_argument("--output", "-o", help="Exporter les séquences vers un fichier JSONL")
    p_pack.add_argument("--limit", type=int, default=None, help="Nombre max de séquences à exporter")

    # loop filter
    p_filt = subparsers.add_parser("filter", help="Filtrer et exporter")
    p_filt.add_argument("file")
    p_filt.add_argument("--output",      "-o")
    p_filt.add_argument("--min-quality", "-q", type=float, default=None)
    p_filt.add_argument("--split",       "-s", choices=["train", "val", "test"])

    # loop count
    p_count = subparsers.add_parser("count", help="Compter les records (avec filtres optionnels)")
    p_count.add_argument("file")
    p_count.add_argument("--min-quality", "-q", type=float, default=None)
    p_count.add_argument("--split",       "-s", choices=["train", "val", "test"])

    # loop merge
    p_merge = subparsers.add_parser("merge", help="Fusionner plusieurs fichiers .loop")
    p_merge.add_argument("files",  nargs="+", help="Fichiers .loop à fusionner")
    p_merge.add_argument("--output", "-o", required=True, help="Fichier de sortie (.loop)")
    p_merge.add_argument("--name",         help="Nom du dataset fusionné")

    # loop inspect
    p_inspect = subparsers.add_parser("inspect", help="Inspecter un record spécifique")
    p_inspect.add_argument("file", help="Fichier .loop")
    p_inspect.add_argument("--record", "-r", type=int, default=None, help="Index du record à inspecter")
    p_inspect.add_argument("--sample", "-s", type=int, default=3, help="Nombre d'enregistrements à échantillonner (défaut: 3)")
    p_inspect.add_argument("--full", "-f", action="store_true", help="Afficher le contenu complet des messages")

    # loop patch create
    p_patch_create = subparsers.add_parser("patch-create", help="Créer un fichier patch (.looppatch)")
    p_patch_create.add_argument("base", help="Fichier .loop de base")
    p_patch_create.add_argument("records", help="Fichier JSONL avec les nouveaux records")
    p_patch_create.add_argument("-o", "--output", required=True, help="Fichier patch de sortie (.looppatch)")

    # loop patch apply
    p_patch_apply = subparsers.add_parser("patch-apply", help="Appliquer un fichier patch (.looppatch)")
    p_patch_apply.add_argument("base", help="Fichier .loop de base")
    p_patch_apply.add_argument("patch", help="Fichier patch (.looppatch)")
    p_patch_apply.add_argument("-o", "--output", required=True, help="Fichier .loop fusionné de sortie")

    # loop diff
    p_diff = subparsers.add_parser("diff", help="Comparer deux fichiers .loop")
    p_diff.add_argument("file_a", help="Premier fichier .loop")
    p_diff.add_argument("file_b", help="Deuxième fichier .loop")

    args = parser.parse_args()

    commands = {
        "info":     cmd_info,
        "validate": cmd_validate,
        "convert":  cmd_convert,
        "stats":    cmd_stats,
        "filter":   cmd_filter,
        "count":    cmd_count,
        "merge":    cmd_merge,
        "pack":     cmd_pack,
        "inspect":  cmd_inspect,
        "patch-create": cmd_patch_create,
        "patch-apply":  cmd_patch_apply,
        "diff":     cmd_diff,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
