"""
StreamingLoopWriter — Écriture streaming de fichiers .loop pour datasets volumineux

Contrairement à LoopWriter qui bufferise tout en mémoire, StreamingLoopWriter
écrit les blocs sur disque au fur et à mesure, permettant de traiter des datasets
de taille arbitraire sans épuiser la RAM.

Exemple :
    writer = StreamingLoopWriter("huge_dataset.loop", metadata={...})
    
    for record in huge_iterator:
        writer.add(record)
    
    writer.finalize()  # Écrit l'index, les métadonnées et le footer
"""

from __future__ import annotations

import json
import struct
import logging
import time
import tempfile
import os
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, BinaryIO

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
from looplib.utils import crc64, schema_hash

logger = logging.getLogger(__name__)


class StreamingLoopWriter:
    """
    Écrit un fichier .loop en mode streaming — pas de buffer mémoire illimité.
    
    Les blocs sont écrits immédiatement sur disque (dans un fichier temporaire),
    et l'index est reconstruit à la finalisation.
    
    Args:
        path: Chemin du fichier .loop final.
        metadata: Métadonnées du dataset.
        block_size: Nombre de records par bloc.
        validate: Si True, valide chaque record.
    """

    SCHEMA = {
        "roles": ["system", "user", "assistant", "tool", "function"],
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
        self.path = Path(path)
        self.metadata = metadata or {}
        self.block_size = block_size
        self.validate = validate

        self._validator = LoopValidator()
        self._compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL)

        # Temporary file for data blocks (written sequentially)
        self._temp_fd: Optional[BinaryIO] = None
        self._temp_path: Optional[Path] = None

        # Current block buffer (small, flushed regularly)
        self._records: List[Dict] = []
        
        # Block metadata for index reconstruction
        self._block_meta: List[Dict] = []
        self._crc_data = b""

        # Stats
        self._n_records = 0
        self._total_tokens = 0
        self._quality_scores: List[float] = []
        self._splits_count = {0: 0, 1: 0, 2: 0}
        self._sources: set = set()
        self._tags: set = set()

        # Initialize temp file
        self._init_temp_file()

    def _init_temp_file(self) -> None:
        """Crée le fichier temporaire pour les blocs de données."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, self._temp_path = tempfile.mkstemp(
            suffix=".loop.tmp", 
            prefix="loop_stream_",
            dir=self.path.parent
        )
        self._temp_fd = os.fdopen(fd, "wb")
        logger.debug(f"Temp file: {self._temp_path}")

    def add(self, record: Dict[str, Any]) -> "StreamingLoopWriter":
        """Ajoute un record au dataset."""
        if self.validate:
            self._validator.validate(record)

        # Update stats
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
        split_id = SPLIT_IDS.get(split_name, 0)
        self._splits_count[split_id] = self._splits_count.get(split_id, 0) + 1

        self._records.append(record)

        # Flush block when full
        if len(self._records) >= self.block_size:
            self._flush_block()

        return self

    def add_many(self, records: List[Dict[str, Any]]) -> "StreamingLoopWriter":
        """Ajoute plusieurs records d'un coup."""
        for record in records:
            self.add(record)
        return self

    def _flush_block(self) -> None:
        """Compresse et écrit le bloc courant sur disque."""
        if not self._records or self._temp_fd is None:
            return

        block_idx = len(self._block_meta)

        # Determine dominant split
        split_counts = {}
        for r in self._records:
            s = SPLIT_IDS.get(r.get("split", "train"), 0)
            split_counts[s] = split_counts.get(s, 0) + 1
        dominant_split = max(split_counts, key=split_counts.get)

        # Serialize records
        raw_parts = []
        for record in self._records:
            record_bytes = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            if len(record_bytes) > MAX_RECORD_SIZE:
                raise ValueError(f"Record trop grand : {len(record_bytes)} bytes > {MAX_RECORD_SIZE} max")
            raw_parts.append(struct.pack("<I", len(record_bytes)))
            raw_parts.append(record_bytes)

        block_header = MAGIC_BLOCK + struct.pack("<I", block_idx)
        uncompressed = block_header + b"".join(raw_parts)

        # Accumulate for CRC
        self._crc_data += uncompressed

        compressed = self._compressor.compress(uncompressed)
        
        # Write to temp file and store metadata
        block_offset = self._temp_fd.tell()
        self._temp_fd.write(compressed)
        
        self._block_meta.append({
            "offset": block_offset,
            "compressed_size": len(compressed),
            "uncompressed_size": len(uncompressed),
            "n_records": len(self._records),
            "split_id": dominant_split,
        })

        self._records = []

    def finalize(self) -> int:
        """
        Finalise le fichier .loop — écrit l'index, métadonnées et footer.
        
        Returns:
            Taille du fichier final en bytes.
        """
        # Flush remaining records
        if self._records:
            self._flush_block()

        if not self._block_meta:
            raise ValueError("Impossible de sauvegarder un .loop vide (0 records).")

        if self._temp_fd is None:
            raise RuntimeError("Writer already finalized")

        # Close temp file for reading
        self._temp_fd.close()

        # Calculate CRC
        crc = crc64(self._crc_data)

        # Build metadata
        full_metadata = self._build_metadata()
        meta_json = json.dumps(full_metadata, ensure_ascii=False, separators=(",", ":"))
        meta_bytes = self._compressor.compress(meta_json.encode("utf-8"))

        # Calculate final layout
        index_offset = HEADER_SIZE
        index_size = len(self._block_meta) * INDEX_ENTRY_SIZE
        blocks_start = index_offset + index_size

        # Adjust block offsets (they were relative to temp file start)
        for bm in self._block_meta:
            bm["final_offset"] = blocks_start + bm["offset"]

        metadata_offset = blocks_start + sum(bm["compressed_size"] for bm in self._block_meta)

        # Write final file
        with open(self.path, "wb") as f:
            # Header
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
                len(self._block_meta),
                metadata_offset,
                int(time.time()),
                schema_hash(self.SCHEMA),
                b"\x00" * 16,
            )
            f.write(header)

            # Index
            for bm in self._block_meta:
                entry = (
                    struct.pack("<Q", bm["final_offset"]) +
                    struct.pack("<I", bm["compressed_size"]) +
                    struct.pack("<I", bm["uncompressed_size"]) +
                    struct.pack("<I", bm["n_records"]) +
                    struct.pack("<H", bm["split_id"]) +
                    struct.pack("<H", 0)
                )
                f.write(entry)

            # Copy blocks from temp file
            with open(self._temp_path, "rb") as temp_f:
                while True:
                    chunk = temp_f.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)

            # Metadata
            f.write(meta_bytes)

            # Footer
            footer = (
                struct.pack("<I", len(meta_bytes)) +
                struct.pack("<Q", crc) +
                MAGIC_FOOTER
            )
            f.write(footer)

        # Cleanup temp file
        os.unlink(self._temp_path)
        self._temp_path = None
        self._temp_fd = None

        size = self.path.stat().st_size
        logger.info(
            f"Saved {self.path} — {self._n_records} records, "
            f"{len(self._block_meta)} blocs, {size / 1024:.1f} KB"
        )
        return size

    def _build_metadata(self) -> Dict[str, Any]:
        """Construit les métadonnées finales."""
        quality_stats = {}
        if self._quality_scores:
            qs = sorted(self._quality_scores)
            n = len(qs)
            quality_stats = {
                "mean": round(sum(qs) / n, 4),
                "min": round(qs[0], 4),
                "max": round(qs[-1], 4),
                "p25": round(qs[n // 4], 4),
                "p75": round(qs[3 * n // 4], 4),
            }

        splits = {
            "train": self._splits_count.get(0, 0),
            "val": self._splits_count.get(1, 0),
            "test": self._splits_count.get(2, 0),
        }

        meta = {
            "loop_format_version": "1.0",
            "n_records": self._n_records,
            "n_blocks": len(self._block_meta),
            "block_size": self.block_size,
            "compression": "zstd",
            "schema": self.SCHEMA,
            "splits": splits,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        if self._total_tokens > 0:
            meta["total_tokens_approx"] = self._total_tokens
            meta["avg_tokens_per_record"] = round(self._total_tokens / self._n_records)
        if quality_stats:
            meta["quality_stats"] = quality_stats
        if self._sources:
            meta["sources"] = sorted(self._sources)
        if self._tags:
            meta["tags"] = sorted(self._tags)

        meta.update(self.metadata)
        return meta

    def __repr__(self) -> str:
        """Représentation concise pour debugging."""
        n_blocks_finalized = len(self._block_meta)
        n_buffered = len(self._records)
        finalized = " (finalized)" if self._temp_fd is None else ""
        return (
            f"<StreamingLoopWriter path='{self.path.name}'{finalized} "
            f"records_added={self._n_records:,} "
            f"blocks={n_blocks_finalized} "
            f"buffered={n_buffered}>"
        )

    def __enter__(self) -> "StreamingLoopWriter":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Cleanup temp file on exception."""
        if self._temp_fd is not None:
            try:
                self._temp_fd.close()
            except:
                pass
        if self._temp_path is not None and os.path.exists(self._temp_path):
            try:
                os.unlink(self._temp_path)
            except:
                pass
