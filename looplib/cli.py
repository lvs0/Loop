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

import sys
import json
import time
import struct
import logging
import argparse
from pathlib import Path

logging.basicConfig(format="[loop] %(levelname)s: %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)


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

    # 3. Lecture de tous les blocs
    total_records = 0
    start = time.time()
    try:
        for block_idx in range(reader._header["n_blocks"]):
            records = reader.read_block(block_idx)
            total_records += len(records)
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

    with open(input_path, "r", encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
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


def cmd_stats(args) -> None:
    """Affiche des statistiques détaillées."""
    from looplib.reader import LoopReader

    reader = LoopReader(args.file)
    info   = reader.info()

    print(f"\nStatistiques : {args.file}")
    print(f"{'─' * 40}")

    # Distribution des qualités
    quality_buckets = {f"{i/10:.1f}-{(i+1)/10:.1f}": 0 for i in range(10)}
    total = 0
    tokens_total = 0
    tags_count   = {}
    lang_count   = {}
    split_count  = {"train": 0, "val": 0, "test": 0}

    for record in reader.stream():
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
        max_len = 2048  # assumption
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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="loop",
        description="Outil CLI pour le format .loop",
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

    args = parser.parse_args()

    commands = {
        "info":     cmd_info,
        "validate": cmd_validate,
        "convert":  cmd_convert,
        "stats":    cmd_stats,
        "filter":   cmd_filter,
        "count":    cmd_count,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
