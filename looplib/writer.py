"""
LoopWriter — Écriture de fichiers .loop

Exemple d'utilisation :
    writer = LoopWriter("mon_dataset.loop", metadata={
        "name": "coding_fr_v1",
        "category": "code",
        "language": "fr",
    })

    writer.add({
        "messages": [
            {"role": "system",    "content": "Tu es un expert Python."},
            {"role": "user",      "content": "Comment lire un CSV ?"},
            {"role": "assistant", "content": "Utilise pandas.read_csv() ..."}
        ],
        "quality": 0.82,
        "tags": ["python", "csv", "pandas"],
        "split": "train"
    })

    writer.save()
"""

from __future__ import annotations

import json
import struct
import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import zstandard as zstd

from looplib.constants import (
    MAGIC_HEADER, MAGIC_FOOTER, MAGIC_BLOCK,
    HEADER_SIZE, INDEX_ENTRY_SIZE, FOOTER_SIZE,
    FORMAT_VERSION_MAJOR, FORMAT_VERSION_MINOR,
    FLAG_COMPRESSION_ZSTD, FLAG_MULTI_SPLIT,
    SPLIT_IDS, SPLIT_ALL,
    MAX_RECORD_SIZE, MAX_BLOCK_SIZE, ZSTD_LEVEL,
)
from looplib.validator import LoopValidator, ValidationError

logger = logging.getLogger(__name__)


def _crc64(data: bytes) -> int:
    """CRC64/ECMA-182 via table polynomiale."""
    poly  = 0xC96C5795D7870F42
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ (poly if crc & 1 else 0)
        table.append(crc)

    crc = 0xFFFFFFFFFFFFFFFF
    for byte in data:
        crc = table[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFFFFFFFFFF


def _schema_hash(schema: dict) -> int:
    """Hash MD5 tronqué à 4 bytes du schéma pour détection d'incompatibilité."""
    raw  = json.dumps(schema, sort_keys=True).encode("utf-8")
    md5  = hashlib.md5(raw).digest()
    return struct.unpack("<I", md5[:4])[0]


class LoopWriter:
    """
    Écrit un fichier .loop à partir d'une séquence de records de conversation.

    Le fichier est construit en mémoire par blocs puis écrit d'un seul coup
    lors de l'appel à .save(). Pour des datasets très larges (>10GB), utiliser
    StreamingLoopWriter.
    
    Example:
        writer = LoopWriter("output.loop", metadata={"name": "my_dataset"})
        for record in records:
            writer.add(record)
        writer.save()
    """

    SCHEMA = {
        "roles":           ["system", "user", "assistant", "tool", "function"],
        "required_fields": ["messages"],
        "optional_fields": ["quality", "source", "language", "tags", "tokens", "split"],
    }

    def __init__(
        self,
        path: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
        block_size: int = MAX_BLOCK_SIZE,
        validate: bool = True,
    ) -> None:
        """
        Args:
            path:       Chemin du fichier .loop à créer.
            metadata:   Métadonnées globales du dataset (name, category, language, etc.)
            block_size: Nombre de records par bloc (défaut 512).
            validate:   Si True, valide chaque record à l'ajout.
        """
        self.path       = Path(path)
        self.metadata   = metadata or {}
        self.block_size = block_size
        self.validate   = validate

        self._records:      List[Dict] = []   # buffer courant
        self._blocks:       List[bytes] = []  # blocs compressés finalisés
        self._block_meta:   List[Dict] = []   # stats par bloc
        self._validator     = LoopValidator()
        self._compressor    = zstd.ZstdCompressor(level=ZSTD_LEVEL)

        # Stats globales
        self._n_records      = 0
        self._total_tokens   = 0
        self._quality_scores: List[float] = []
        self._splits_count   = {0: 0, 1: 0, 2: 0}  # train/val/test
        self._sources        = set()
        self._tags           = set()
        self._crc_data       = b""  # accumulation pour CRC64 final

    def __repr__(self) -> str:
        """Représentation concise pour debugging."""
        n_blocks_finalized = len(self._blocks)
        n_buffered = len(self._records)
        return (
            f"<LoopWriter path='{self.path.name}' "
            f"records_added={self._n_records:,} "
            f"blocks={n_blocks_finalized} "
            f"buffered={n_buffered}>"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def add(self, record: Dict[str, Any]) -> "LoopWriter":
        """
        Ajoute un record au dataset.

        Args:
            record: Dictionnaire avec au minimum la clé "messages".

        Returns:
            self (chaînable)

        Raises:
            ValidationError: Si validate=True et que le record est invalide.
        """
        if self.validate:
            self._validator.validate(record)

        # Mise à jour stats
        self._n_records += 1
        if "quality" in record:
            self._quality_scores.append(float(record["quality"]))
        if "tokens" in record:
            self._total_tokens += int(record["tokens"])
        if "source" in record:
            self._sources.add(str(record["source"]))
        if "tags" in record:
            self._tags.update(record["tags"])

        split_name = record.get("split", "train")
        split_id   = SPLIT_IDS.get(split_name, 0)
        self._splits_count[split_id] = self._splits_count.get(split_id, 0) + 1

        self._records.append(record)

        # Flush automatique quand le bloc est plein
        if len(self._records) >= self.block_size:
            self._flush_block()

        return self

    def add_many(self, records: List[Dict[str, Any]]) -> "LoopWriter":
        """Ajoute plusieurs records d'un coup."""
        for record in records:
            self.add(record)
        return self

    def save(self) -> int:
        """
        Écrit le fichier .loop complet sur disque.

        Returns:
            Taille du fichier en bytes.

        Raises:
            IOError: Si le fichier ne peut pas être créé.
        """
        # Vider le buffer restant
        if self._records:
            self._flush_block()

        if not self._blocks:
            raise ValueError("Impossible de sauvegarder un .loop vide (0 records).")

        # Calcul du CRC64 sur tous les blocs décompressés accumulés
        crc = _crc64(self._crc_data)

        # Préparer les métadonnées finales
        full_metadata = self._build_metadata()
        meta_json     = json.dumps(full_metadata, ensure_ascii=False, separators=(",", ":"))
        meta_bytes    = self._compressor.compress(meta_json.encode("utf-8"))

        # Calcul des offsets
        index_offset    = HEADER_SIZE
        index_size      = len(self._blocks) * INDEX_ENTRY_SIZE
        blocks_start    = index_offset + index_size

        block_offsets = []
        cursor = blocks_start
        for block in self._blocks:
            block_offsets.append(cursor)
            cursor += len(block)

        metadata_offset = cursor

        # ── Écriture du fichier ───────────────────────────────────────────────
        self.path.parent.mkdir(parents=True, exist_ok=True)

        with open(self.path, "wb") as f:

            # HEADER (64 bytes)
            flags = FLAG_COMPRESSION_ZSTD
            multi_split = sum(1 for v in self._splits_count.values() if v > 0) > 1
            if multi_split:
                flags |= FLAG_MULTI_SPLIT

            header = struct.pack(
                "<4sHHHHqqqqI16s",
                MAGIC_HEADER,
                FORMAT_VERSION_MAJOR,
                FORMAT_VERSION_MINOR,
                flags,
                self.block_size,
                self._n_records,
                len(self._blocks),
                metadata_offset,
                int(time.time()),
                _schema_hash(self.SCHEMA),
                b"\x00" * 16,  # reserved
            )
            assert len(header) == HEADER_SIZE, f"Header size mismatch: {len(header)}"
            f.write(header)

            # INDEX (n_blocs × 24 bytes)
            for i, (block, offset) in enumerate(zip(self._blocks, block_offsets)):
                bm = self._block_meta[i]
                entry = struct.pack(
                    "<QIIIHHx",  # pad 1 byte pour aligner sur 24
                    offset,
                    len(block),
                    bm["uncompressed_size"],
                    bm["n_records"],
                    bm["split_id"],
                    0,  # reserved
                )
                # struct.pack ci-dessus = 8+4+4+4+2+2+padding = 25... recalcul
                # On écrit manuellement pour être exact sur 24 bytes
                entry = (
                    struct.pack("<Q", offset) +
                    struct.pack("<I", len(block)) +
                    struct.pack("<I", bm["uncompressed_size"]) +
                    struct.pack("<I", bm["n_records"]) +
                    struct.pack("<H", bm["split_id"]) +
                    struct.pack("<H", 0)  # reserved
                )
                assert len(entry) == INDEX_ENTRY_SIZE
                f.write(entry)

            # BLOCS
            for block in self._blocks:
                f.write(block)

            # METADATA
            f.write(meta_bytes)

            # FOOTER (16 bytes)
            footer = (
                struct.pack("<I", len(meta_bytes)) +
                struct.pack("<Q", crc) +
                MAGIC_FOOTER
            )
            assert len(footer) == FOOTER_SIZE
            f.write(footer)

        size = self.path.stat().st_size
        logger.info(
            f"Saved {self.path} — {self._n_records} records, "
            f"{len(self._blocks)} blocs, {size / 1024:.1f} KB"
        )
        return size

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _flush_block(self) -> None:
        """Compresse et finalise le bloc courant."""
        if not self._records:
            return

        block_idx = len(self._blocks)

        # Déterminer le split majoritaire du bloc
        split_counts = {}
        for r in self._records:
            s = SPLIT_IDS.get(r.get("split", "train"), 0)
            split_counts[s] = split_counts.get(s, 0) + 1
        dominant_split = max(split_counts, key=split_counts.get)

        # Sérialisation des records
        raw_parts = []
        for record in self._records:
            record_bytes = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(record_bytes) > MAX_RECORD_SIZE:
                raise ValueError(
                    f"Record trop grand : {len(record_bytes)} bytes > {MAX_RECORD_SIZE} bytes max"
                )
            raw_parts.append(struct.pack("<I", len(record_bytes)))
            raw_parts.append(record_bytes)

        block_header = MAGIC_BLOCK + struct.pack("<I", block_idx)
        uncompressed = block_header + b"".join(raw_parts)

        # Accumuler pour CRC
        self._crc_data += uncompressed

        compressed = self._compressor.compress(uncompressed)

        self._blocks.append(compressed)
        self._block_meta.append({
            "n_records":        len(self._records),
            "uncompressed_size": len(uncompressed),
            "split_id":         dominant_split,
        })

        self._records = []

    def _build_metadata(self) -> Dict[str, Any]:
        """Construit le dictionnaire de métadonnées complètes."""
        quality_stats = {}
        if self._quality_scores:
            qs = sorted(self._quality_scores)
            n  = len(qs)
            quality_stats = {
                "mean":  round(sum(qs) / n, 4),
                "min":   round(qs[0], 4),
                "max":   round(qs[-1], 4),
                "p25":   round(qs[n // 4], 4),
                "p75":   round(qs[3 * n // 4], 4),
            }

        splits = {
            "train": self._splits_count.get(0, 0),
            "val":   self._splits_count.get(1, 0),
            "test":  self._splits_count.get(2, 0),
        }

        meta = {
            "loop_format_version": "1.0",
            "n_records":           self._n_records,
            "n_blocks":            len(self._blocks),
            "block_size":          self.block_size,
            "compression":         "zstd",
            "schema":              self.SCHEMA,
            "splits":              splits,
            "created_at":          time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if self._total_tokens > 0:
            meta["total_tokens_approx"]   = self._total_tokens
            meta["avg_tokens_per_record"] = round(self._total_tokens / self._n_records)
        if quality_stats:
            meta["quality_stats"] = quality_stats
        if self._sources:
            meta["sources"] = sorted(self._sources)
        if self._tags:
            meta["tags"] = sorted(self._tags)

        # Fusionner avec les métadonnées utilisateur
        meta.update(self.metadata)

        return meta

    # ──────────────────────────────────────────────────────────────────────────
    # Fusion & Append
    # ──────────────────────────────────────────────────────────────────────────

    @classmethod
    def merge(cls, paths: List[Path], output_path: Path, metadata: Optional[Dict[str, Any]] = None) -> Path:
        """Fusionne plusieurs fichiers .loop en un seul.

        Les blocs de chaque fichier sont recompressés et réécrits dans
        le fichier de sortie. Les métadonnées de chaque source sont
        agrégées (``sources``).

        Args:
            paths: Liste des fichiers .loop à fusionner (dans l'ordre).
            output_path: Chemin du fichier de sortie.
            metadata: Métadonnées additionnelles (optionnel).

        Returns:
            Le ``output_path``.
        """
        if len(paths) < 2:
            raise ValueError("Il faut au moins 2 fichiers à fusionner.")
        for p in paths:
            if not p.exists():
                raise FileNotFoundError(p)

        from .reader import LoopReader

        meta: Dict[str, Any] = dict(metadata or {})
        meta["name"] = meta.get("name", "merged")

        writer = cls(output_path, metadata=meta)
        sources: List[str] = []
        total_tokens = 0
        splits_count: Dict[int, int] = {0: 0, 1: 0, 2: 0}
        quality_scores: List[float] = []

        for p in paths:
            reader = LoopReader(p)
            h = reader._header
            m = reader.metadata  # lire via la property (parse si nécessaire)
            total_tokens += h.get("total_tokens_approx", 0)
            src_name = (m or {}).get("name", str(p))
            sources.append(src_name)

            for rec in reader.stream():
                q = rec.get("quality")
                if q is not None:
                    quality_scores.append(q)
                s = rec.get("split", "train")
                s_id = SPLIT_IDS.get(s, 0)
                splits_count[s_id] = splits_count.get(s_id, 0) + 1
                writer.add(rec)

            if hasattr(reader, "close"):
                reader.close()

        writer.save()

        # Réécrire les métadonnées avec les stats agrégées
        _rewrite_metadata(output_path, {
            "loop_format_version": "1.0",
            "n_records": writer._n_records,
            "n_blocks": len(writer._blocks),
            "block_size": writer.block_size,
            "compression": "zstd",
            "schema": writer.SCHEMA,
            "splits": {
                "train": splits_count.get(0, 0),
                "val": splits_count.get(1, 0),
                "test": splits_count.get(2, 0),
            },
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "sources": sorted(set(sources)),
            "total_tokens_approx": total_tokens,
            "quality_stats": (
                {
                    "mean": round(sum(quality_scores) / len(quality_scores), 4),
                    "min": round(min(quality_scores), 4),
                    "max": round(max(quality_scores), 4),
                }
                if quality_scores
                else {}
            ),
            **meta,
        })

        logger.info(f"Merged {len(paths)} files → {output_path} ({writer._n_records} records)")
        return output_path

    def append(self, record: Dict[str, Any]) -> "LoopWriter":
        """Ajoute un record à un fichier existant (mode append).

        Après ``append()``, le fichier est relu en lecture seule via ``get_reader()``.
        """
        self._append_mode = True
        return self.add(record)

    def finalize_append(self) -> Path:
        """Finalise le mode append."""
        raise NotImplementedError(
            "append() est un chemin de compatibilité. "
            "Pour ajouter à un fichier existant, recarga-le et réécris-le avec add(). "
            "Exemple : reader = LoopReader(existing.loop); writer = LoopWriter(new.loop); "
            "writer.add_many(reader.stream()); writer.save()"
        )

    def get_reader(self) -> "LoopReader":
        """Retourne un LoopReader sur le fichier en cours (mode append)."""
        if not self._append_mode:
            raise RuntimeError("get_reader() n'est disponible qu'après append().")
        from .reader import LoopReader

        return LoopReader(self.path)

    def __enter__(self) -> "LoopWriter":
        """Context manager entry —returns self for use with 'with' statement."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit — no cleanup needed since save() handles everything."""
        pass


def _rewrite_metadata(path: Path, metadata: Dict[str, Any]) -> None:
    """Réécrit les métadonnées d'un fichier .loop sans modifier les blocs compressés."""
    with open(path, "rb+") as f:
        header = f.read(HEADER_SIZE)
        # Header format: <4sHHHHqqqqI16s
        # bytes 12-19: n_records (q), bytes 20-27: n_blocks (q), bytes 28-35: metadata_offset (q)
        n_records = int.from_bytes(header[12:20], "little")
        n_blocks = int.from_bytes(header[20:28], "little")
        index_offset = HEADER_SIZE  # toujours 64
        index_size = n_blocks * INDEX_ENTRY_SIZE

        # Lire l'index pour obtenir les positions des blocs
        f.seek(index_offset)
        index_data = f.read(index_size)

        # Lire les blocs compressés en utilisant les offsets de l'index
        blocks: List[bytes] = []
        for bi in range(n_blocks):
            entry = index_data[bi * INDEX_ENTRY_SIZE: (bi + 1) * INDEX_ENTRY_SIZE]
            offset = int.from_bytes(entry[0:8], "little")
            size = int.from_bytes(entry[8:12], "little")
            f.seek(offset)
            blocks.append(f.read(size))

        # CRC sur les blocs compressés
        crc_data = b"".join(blocks)
        crc = _crc64(crc_data)

        # Préparer les nouvelles métadonnées
        meta_json = json.dumps(metadata, ensure_ascii=False, separators=(",", ":"))
        cctx = zstd.ZstdCompressor(level=ZSTD_LEVEL)
        meta_bytes = cctx.compress(meta_json.encode("utf-8"))

        # Réécrire header + index + blocs + métadonnées + footer
        f.seek(0)
        f.write(header)  # header inchangé
        f.write(index_data)  # index recopié
        for block in blocks:
            f.write(block)  # blocs recopiés
        f.write(meta_bytes)  # nouvelles métadonnées
        footer = (
            struct.pack("<I", len(meta_bytes)) +
            struct.pack("<Q", crc) +
            MAGIC_FOOTER
        )
        f.write(footer)
        f.truncate()
