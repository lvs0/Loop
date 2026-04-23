"""
LoopReader — Lecture streaming de fichiers .loop

Exemple :
    reader = LoopReader("coding_fr.loop")
    print(reader.info())

    # Stream filtré par qualité et split
    for record in reader.stream(min_quality=0.70, split="train"):
        messages = record["messages"]

    # Lecture d'un bloc précis (random access)
    records = reader.read_block(7)

    # Export vers JSONL
    reader.to_jsonl("output.jsonl", min_quality=0.75)
"""

import json
import struct
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Iterator

import zstandard as zstd

from looplib.constants import (
    MAGIC_HEADER, MAGIC_FOOTER, MAGIC_BLOCK,
    HEADER_SIZE, INDEX_ENTRY_SIZE, FOOTER_SIZE,
    FORMAT_VERSION_MAJOR,
    SPLIT_IDS, SPLIT_NAMES, SPLIT_ALL,
    FLAG_COMPRESSION_ZSTD,
    MAX_RECORD_SIZE,
)

logger = logging.getLogger(__name__)


class LoopParseError(Exception):
    """Erreur de parsing d'un fichier .loop."""
    pass


class LoopReader:
    """
    Lit un fichier .loop de façon streaming, avec random access via l'index.

    Le fichier n'est jamais chargé entièrement en RAM.
    La lecture se fait bloc par bloc, le bloc courant étant le seul en mémoire.

    Example:
        reader = LoopReader("dataset.loop")
        for record in reader.stream(min_quality=0.8):
            print(record["messages"])
    """

    def __init__(self, path: str | Path) -> None:
        self.path        = Path(path)
        self._decompressor = zstd.ZstdDecompressor()
        self._header     = None
        self._index      = None
        self._metadata   = None
        self._file_size  = 0

        self._parse_header_and_index()

    def __repr__(self) -> str:
        """Représentation concise pour debugging."""
        if self._header:
            return (
                f"<LoopReader path='{self.path.name}' "
                f"records={self._header['n_records']:,} "
                f"blocks={self._header['n_blocks']}>"
            )
        return f"<LoopReader path='{self.path}' (uninitialized)>"

    # ──────────────────────────────────────────────────────────────────────────
    # API publique
    # ──────────────────────────────────────────────────────────────────────────

    def info(self) -> Dict[str, Any]:
        """Retourne un dictionnaire résumant le fichier."""
        meta = self.metadata
        return {
            "path":              str(self.path),
            "file_size_mb":      round(self._file_size / 1024 / 1024, 2),
            "n_records":         self._header["n_records"],
            "n_blocks":          self._header["n_blocks"],
            "block_size":        self._header["block_size"],
            "format_version":    f"{self._header['version_major']}.{self._header['version_minor']}",
            "compression":       "zstd" if self._header["flags"] & FLAG_COMPRESSION_ZSTD else "none",
            "name":              meta.get("name", "(sans nom)"),
            "category":          meta.get("category", "?"),
            "language":          meta.get("language", "?"),
            "splits":            meta.get("splits", {}),
            "quality_stats":     meta.get("quality_stats", {}),
            "total_tokens":      meta.get("total_tokens_approx", 0),
            "tags":              meta.get("tags", []),
            "sources":           meta.get("sources", []),
            "created_at":        meta.get("created_at", "?"),
        }

    def stream(
        self,
        min_quality:  Optional[float] = None,
        max_quality:  Optional[float] = None,
        split:        Optional[str]   = None,
        language:     Optional[str]   = None,
        tags:         Optional[List[str]] = None,
    ) -> Iterator[Dict[str, Any]]:
        """
        Itère sur les records du fichier avec filtrage optionnel.

        Streaming pur : seul le bloc en cours de lecture est en RAM.

        Args:
            min_quality: Score qualité minimum (0.0–1.0).
            max_quality: Score qualité maximum.
            split:       "train", "val", "test", ou None (tous).
            language:    Code de langue ISO 639-1 (ex: "fr").
            tags:        Liste de tags — le record doit avoir AU MOINS un de ces tags.

        Yields:
            dict record valide correspondant aux filtres.
        """
        target_split_id = SPLIT_IDS.get(split) if split else None
        tags_set        = set(tags) if tags else None

        for block_idx in range(self._header["n_blocks"]):
            index_entry = self._index[block_idx]

            # Note: block-level split filtering is skipped because a block's dominant split
            # may differ from individual record splits. Record-level filter handles this correctly.

            for record in self._read_block_raw(block_idx):
                # Filtrage qualité
                if min_quality is not None:
                    if record.get("quality", 1.0) < min_quality:
                        continue
                if max_quality is not None:
                    if record.get("quality", 0.0) > max_quality:
                        continue
                # Filtrage split au niveau record
                if target_split_id is not None:
                    record_split = SPLIT_IDS.get(record.get("split", "train"), 0)
                    if record_split != target_split_id:
                        continue
                # Filtrage langue
                if language is not None:
                    if record.get("language", "") != language:
                        continue
                # Filtrage tags
                if tags_set is not None:
                    record_tags = set(record.get("tags", []))
                    if not tags_set.intersection(record_tags):
                        continue

                yield record

    def read_block(self, block_idx: int) -> List[Dict[str, Any]]:
        """
        Lit un bloc spécifique par son index.

        Args:
            block_idx: Index du bloc (0 à n_blocks-1).

        Returns:
            Liste de records du bloc.
        """
        return list(self._read_block_raw(block_idx))

    def count(
        self,
        min_quality: Optional[float] = None,
        max_quality: Optional[float] = None,
        split:       Optional[str]   = None,
        language:    Optional[str]   = None,
        tags:        Optional[List[str]] = None,
    ) -> int:
        """
        Compte les records correspondant aux filtres sans les charger tous.

        Si aucun filtre n'est donné, retourne directement n_records du header.
        """
        if all(x is None for x in (min_quality, max_quality, split, language, tags)):
            return self._header["n_records"]

        return sum(
            1
            for _ in self.stream(
                min_quality=min_quality,
                max_quality=max_quality,
                split=split,
                language=language,
                tags=tags,
            )
        )

    def to_list(
        self,
        min_quality: Optional[float] = None,
        max_quality: Optional[float] = None,
        split:       Optional[str]   = None,
        language:    Optional[str]   = None,
        tags:        Optional[List[str]] = None,
        max_records: Optional[int]   = None,
    ) -> List[Dict[str, Any]]:
        """Charge les records (filtrés) en mémoire.

        Args:
            max_records: Si renseigné, limite le nombre de records chargés.
        """
        count = 0
        records = []
        for record in self.stream(
            min_quality=min_quality,
            max_quality=max_quality,
            split=split,
            language=language,
            tags=tags,
        ):
            records.append(record)
            count += 1
            if max_records and count >= max_records:
                break
        return records

    def to_jsonl(
        self,
        output_path:  str | Path,
        min_quality:  Optional[float] = None,
        max_quality:  Optional[float] = None,
        split:        Optional[str]   = None,
        language:     Optional[str]   = None,
        tags:         Optional[List[str]] = None,
    ) -> int:
        """
        Exporte vers JSONL.

        Args:
            output_path: Chemin du fichier JSONL de sortie.
            min_quality: Score qualité minimum (0.0–1.0).
            max_quality: Score qualité maximum.
            split:       "train", "val", "test", ou None (tous).
            language:    Code de langue ISO 639-1 (ex: "fr").
            tags:        Liste de tags — le record doit avoir AU MOINS un de ces tags.

        Returns:
            Nombre de records exportés.
        """
        output_path = Path(output_path)
        count       = 0

        with open(output_path, "w", encoding="utf-8") as f:
            for record in self.stream(
                min_quality=min_quality,
                max_quality=max_quality,
                split=split,
                language=language,
                tags=tags,
            ):
                f.write(json.dumps(record, ensure_ascii=False))
                f.write("\n")
                count += 1

        logger.info(f"Exporté {count} records vers {output_path}")
        return count

    def to_huggingface(
        self,
        min_quality: Optional[float] = None,
        max_quality: Optional[float] = None,
        split:       Optional[str]   = None,
        language:    Optional[str]   = None,
        tags:        Optional[List[str]] = None,
    ):
        """
        Exporte vers un datasets.Dataset HuggingFace via streaming.


        Utilise un générateur lazy qui lit les records directement depuis le
        fichier .loop (sans tout charger en RAM au préalable), permettant
        d'exporter des datasets volumineux sans épuiser la mémoire.

        Args:
            min_quality: Score qualité minimum pour filtrer.
            max_quality: Score qualité maximum pour filtrer.
            split:       Split à exporter ("train", "val", "test").
            language:    Code langue ISO 639-1 (ex: "fr").
            tags:        Liste de tags — le record doit avoir au moins un de ces tags.

        Returns:
            datasets.Dataset configuré pour un entraînement LLM.

        Nécessite : pip install datasets
        """
        try:
            from datasets import Dataset
        except ImportError:
            raise ImportError(
                "Installer HuggingFace datasets : pip install datasets"
            )

        # True lazy generator: reads records on-demand from the .loop file.
        # We capture self.path (picklable Path) rather than self._decompressor
        # (unpicklable zstd decompressor object which multiprocessing can't serialize).
        # Each call to stream() creates a fresh decompressor internally via
        # _read_block_raw(), so this remains memory-efficient.
        path = self.path

        def gen():
            # Must re-instantiate reader here so the generator body is picklable
            # (captures path string, not self with unpicklable decompressor).
            reader = LoopReader(path)
            yield from reader.stream(
                min_quality=min_quality,
                max_quality=max_quality,
                split=split,
                language=language,
                tags=tags,
            )

        return Dataset.from_generator(gen)

    def packed_sequences(
        self,
        tokenizer,
        max_seq_len:  int           = 2048,
        min_quality:  Optional[float] = None,
        split:        Optional[str]   = None,
    ):
        """
        Stream-packed sequences ready for LLM fine-tuning.

        This is a convenience wrapper around SequencePacker that reads directly
        from the .loop file and yields packed sequences, without loading all records
        into RAM.

        Example:
            reader = LoopReader("coding_fr.loop")
            for packed in reader.packed_sequences(tokenizer, max_seq_len=2048, min_quality=0.70):
                input_ids      = packed["input_ids"]       # List[int], length max_seq_len
                labels         = packed["labels"]          # List[int], length max_seq_len, -100 on prompts
                attention_mask = packed["attention_mask"] # List[int], length max_seq_len
                position_ids   = packed["position_ids"]    # List[int], length max_seq_len

        Args:
            tokenizer:    HuggingFace tokenizer (must have apply_chat_template).
            max_seq_len:  Maximum sequence length (default 2048).
            min_quality:  Optional minimum quality filter.
            split:        Optional split filter ("train", "val", "test").

        Yields:
            dict with keys: input_ids, labels, attention_mask, position_ids.
            All values are Python lists of exactly max_seq_len elements.

        Note: Requires the ``transformers`` library. Returns plain lists,
              not torch.Tensors — convert manually if needed for training.
        """
        from looplib.packer import SequencePacker
        packer = SequencePacker(tokenizer, max_seq_len=max_seq_len)
        yield from packer.pack(self.stream(min_quality=min_quality, split=split))

    @property
    def metadata(self) -> Dict[str, Any]:
        """Métadonnées du dataset (chargées paresseusement)."""
        if self._metadata is None:
            self._metadata = self._parse_metadata()
        return self._metadata

    # ──────────────────────────────────────────────────────────────────────────
    # Méthodes internes
    # ──────────────────────────────────────────────────────────────────────────

    def _parse_header_and_index(self) -> None:
        """Parse le header et l'index. Appelé à l'instanciation."""
        if not self.path.exists():
            raise FileNotFoundError(f"Fichier .loop introuvable : {self.path}")

        self._file_size = self.path.stat().st_size

        with open(self.path, "rb") as f:
            # ── Header ──────────────────────────────────────────────────────
            raw_header = f.read(HEADER_SIZE)
            if len(raw_header) < HEADER_SIZE:
                raise LoopParseError(f"Fichier trop petit pour être un .loop valide ({self._file_size} bytes)")

            magic = raw_header[:4]
            if magic != MAGIC_HEADER:
                raise LoopParseError(f"Magic bytes invalides : {magic!r} (attendu {MAGIC_HEADER!r})")

            (
                _magic,
                version_major,
                version_minor,
                flags,
                block_size,
                n_records,
                n_blocks,
                metadata_offset,
                created_at,
                schema_hash,
                _reserved,
            ) = struct.unpack("<4sHHHHqqqqI16s", raw_header)

            if version_major > FORMAT_VERSION_MAJOR:
                raise LoopParseError(
                    f"Version du format non supportée : {version_major}.{version_minor} "
                    f"(cette looplib supporte jusqu'à {FORMAT_VERSION_MAJOR}.x)"
                )

            self._header = {
                "version_major":   version_major,
                "version_minor":   version_minor,
                "flags":           flags,
                "block_size":      block_size,
                "n_records":       n_records,
                "n_blocks":        n_blocks,
                "metadata_offset": metadata_offset,
                "created_at":      created_at,
                "schema_hash":     schema_hash,
            }

            # ── Index ────────────────────────────────────────────────────────
            index = []
            for _ in range(n_blocks):
                raw = f.read(INDEX_ENTRY_SIZE)
                if len(raw) < INDEX_ENTRY_SIZE:
                    raise LoopParseError("Index tronqué — fichier corrompu ?")

                offset, comp_size, uncomp_size, n_rec, split_id, _reserved = struct.unpack(
                    "<QIIIHH", raw
                )
                index.append({
                    "offset":            offset,
                    "compressed_size":   comp_size,
                    "uncompressed_size": uncomp_size,
                    "n_records":         n_rec,
                    "split_id":          split_id,
                })

            self._index = index

            # ── Footer (vérification rapide) ─────────────────────────────────
            f.seek(-FOOTER_SIZE, 2)
            raw_footer = f.read(FOOTER_SIZE)
            magic_end  = raw_footer[-4:]
            if magic_end != MAGIC_FOOTER:
                raise LoopParseError(
                    f"Magic footer invalide : {magic_end!r} (attendu {MAGIC_FOOTER!r}). "
                    "Fichier corrompu ou tronqué."
                )

    def _read_block_raw(self, block_idx: int) -> Iterator[Dict[str, Any]]:
        """Lit et décompresse un bloc, itère sur ses records."""
        if block_idx < 0 or block_idx >= self._header["n_blocks"]:
            raise IndexError(f"Index de bloc hors limites : {block_idx}")

        entry = self._index[block_idx]

        with open(self.path, "rb") as f:
            f.seek(entry["offset"])
            compressed = f.read(entry["compressed_size"])

        raw = self._decompressor.decompress(compressed)

        # Vérifier le magic du bloc
        if raw[:4] != MAGIC_BLOCK:
            raise LoopParseError(f"Magic de bloc invalide (bloc {block_idx})")

        # Sauter block_magic (4) + block_index (4)
        pos = 8

        while pos < len(raw):
            if pos + 4 > len(raw):
                break

            record_len = struct.unpack("<I", raw[pos : pos + 4])[0]
            pos += 4

            if record_len == 0:
                break
            if record_len > MAX_RECORD_SIZE:
                raise LoopParseError(
                    f"Record trop grand dans le bloc {block_idx} : {record_len} bytes"
                )
            if pos + record_len > len(raw):
                raise LoopParseError(f"Record tronqué dans le bloc {block_idx}")

            record_bytes = raw[pos : pos + record_len]
            pos         += record_len

            try:
                record = json.loads(record_bytes.decode("utf-8"))
            except json.JSONDecodeError as exc:
                logger.warning(f"Record JSON invalide dans le bloc {block_idx} : {exc}")
                continue

            yield record

    def _parse_metadata(self) -> Dict[str, Any]:
        """Lit et décompresse les métadonnées depuis leur offset."""
        meta_offset = self._header["metadata_offset"]

        with open(self.path, "rb") as f:
            f.seek(-FOOTER_SIZE, 2)
            raw_footer = f.read(4)
            meta_compressed_size = struct.unpack("<I", raw_footer)[0]

            f.seek(meta_offset)
            compressed = f.read(meta_compressed_size)

        raw  = self._decompressor.decompress(compressed)
        meta = json.loads(raw.decode("utf-8"))
        return meta

    def _parse_footer_crc(self) -> int:
        """Lit le CRC64 du footer (utilisé pour les patches)."""
        with open(self.path, "rb") as f:
            f.seek(-FOOTER_SIZE + 4, 2)  # Skip metadata_size (4 bytes), read CRC (8 bytes)
            raw_crc = f.read(8)
            if len(raw_crc) < 8:
                raise LoopParseError("Footer trop court pour lire le CRC")
            return struct.unpack("<Q", raw_crc)[0]
