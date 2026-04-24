"""
LoopPatcher — Création et application de patches .looppatch

Le format .looppatch permet d'ajouter des données à un fichier .loop existant
sans le réécrire entièrement — utile pour les mises à jour incrémentales.

Usage :
    # Créer un patch
    patcher = LoopPatcher.create("base.loop", "new_data.jsonl", "update.looppatch")
    
    # Appliquer un patch
    LoopPatcher.apply("base.loop", "update.looppatch", "merged.loop")
"""

from __future__ import annotations

import json
import struct
import logging
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Union

import zstandard as zstd

from looplib.constants import (
    MAGIC_BLOCK,
    HEADER_SIZE, INDEX_ENTRY_SIZE, FOOTER_SIZE,
    FORMAT_VERSION_MAJOR, FORMAT_VERSION_MINOR,
    FLAG_COMPRESSION_ZSTD,
    SPLIT_IDS, SPLIT_ALL,
    MAX_RECORD_SIZE, MAX_BLOCK_SIZE, ZSTD_LEVEL,
)
from looplib.reader import LoopReader
from looplib.writer import LoopWriter
from looplib.validator import LoopValidator, ValidationError
from looplib.utils import crc64

logger = logging.getLogger(__name__)

# Magic bytes pour .looppatch
MAGIC_PATCH_HEADER = b"PTCH"
MAGIC_PATCH_FOOTER = b"HCTP"  # PTCH inversé

PATCH_HEADER_SIZE = 32
PATCH_FOOTER_SIZE = 8


class PatchError(Exception):
    """Erreur lors de la création ou application d'un patch."""
    pass


class LoopPatcher:
    """
    Gère la création et l'application de patches .looppatch.
    
    Un patch contient des blocs supplémentaires qui seront ajoutés à la fin
    d'un fichier .loop existant, avec un nouvel index reconstruit.
    """

    def __init__(self):
        self._validator = LoopValidator()
        self._compressor = zstd.ZstdCompressor(level=ZSTD_LEVEL)

    @classmethod
    def create(
        cls,
        base_loop: Union[str, Path],
        new_records_source: Union[str, Path, List[Dict[str, Any]]],
        output_patch: Union[str, Path],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Crée un fichier .looppatch à partir de nouveaux records.
        
        Args:
            base_loop: Chemin du fichier .loop de base (pour vérifier la compatibilité).
            new_records_source: Chemin JSONL/JSON ou liste de records à ajouter.
            output_patch: Chemin du fichier .looppatch à créer.
            metadata: Métadonnées optionnelles pour le patch.
            
        Returns:
            Taille du patch en bytes.
            
        Raises:
            PatchError: Si le fichier base n'existe pas ou si les records sont invalides.
        """
        patcher = cls()
        base_path = Path(base_loop)
        output_path = Path(output_patch)
        
        if not base_path.exists():
            raise PatchError(f"Fichier .loop de base introuvable : {base_path}")
        
        # Lire le CRC du fichier de base pour vérification
        base_reader = LoopReader(base_path)
        base_crc = base_reader._parse_footer_crc()
        
        # Collecter les nouveaux records
        records = patcher._load_records(new_records_source)
        if not records:
            raise PatchError("Aucun record à patcher")
        
        # Valider les records
        for i, record in enumerate(records):
            try:
                patcher._validator.validate(record)
            except ValidationError as e:
                raise PatchError(f"Record {i} invalide : {e}")
        
        # Construire les blocs
        blocks, block_meta, crc_data = patcher._build_blocks(records)
        
        # Écrire le patch
        return patcher._write_patch(
            output_path, base_crc, blocks, block_meta, crc_data, 
            len(records), metadata or {}
        )

    @classmethod
    def apply(
        cls,
        base_loop: Union[str, Path],
        patch_file: Union[str, Path],
        output_loop: Union[str, Path],
    ) -> int:
        """
        Applique un patch .looppatch à un fichier .loop de base.
        
        Args:
            base_loop: Chemin du fichier .loop de base.
            patch_file: Chemin du fichier .looppatch.
            output_loop: Chemin du fichier .loop fusionné à créer.
            
        Returns:
            Taille du fichier fusionné en bytes.
            
        Raises:
            PatchError: Si les CRC ne correspondent pas ou si le patch est corrompu.
        """
        patcher = cls()
        base_path = Path(base_loop)
        patch_path = Path(patch_file)
        output_path = Path(output_loop)
        
        if not base_path.exists():
            raise PatchError(f"Fichier .loop de base introuvable : {base_path}")
        if not patch_path.exists():
            raise PatchError(f"Fichier patch introuvable : {patch_path}")
        
        # Lire le fichier de base
        base_reader = LoopReader(base_path)
        base_crc = base_reader._parse_footer_crc()
        
        # Lire et vérifier le patch
        patch_data = patcher._read_patch(patch_path)
        
        # Vérifier la compatibilité
        if patch_data["source_crc64"] != base_crc:
            raise PatchError(
                f"CRC incompatible ! Le patch a été créé pour une version différente du fichier. "
                f"Attendu: {patch_data['source_crc64']:016x}, trouvé: {base_crc:016x}"
            )
        
        # Fusionner
        return patcher._merge(base_reader, patch_data, output_path)

    def _load_records(
        self, source: Union[str, Path, List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Charge les records depuis une source (fichier ou liste)."""
        if isinstance(source, list):
            return source
        
        source_path = Path(source)
        if not source_path.exists():
            raise PatchError(f"Source introuvable : {source_path}")
        
        records = []
        with open(source_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"Ligne ignorée (JSON invalide) : {e}")
        
        return records

    def _build_blocks(
        self, records: List[Dict[str, Any]], block_size: int = MAX_BLOCK_SIZE
    ) -> tuple:
        """Construit les blocs compressés à partir des records."""
        blocks = []
        block_meta = []
        crc_data = b""
        
        current_records = []
        block_idx = 0
        
        for record in records:
            current_records.append(record)
            
            if len(current_records) >= block_size:
                block, meta, uncompressed = self._compress_block(current_records, block_idx)
                blocks.append(block)
                block_meta.append(meta)
                crc_data += uncompressed
                current_records = []
                block_idx += 1
        
        # Dernier bloc
        if current_records:
            block, meta, uncompressed = self._compress_block(current_records, block_idx)
            blocks.append(block)
            block_meta.append(meta)
            crc_data += uncompressed
        
        return blocks, block_meta, crc_data

    def _compress_block(
        self, records: List[Dict[str, Any]], block_idx: int
    ) -> tuple:
        """Compresse un bloc de records."""
        # Déterminer le split dominant
        split_counts = {}
        for r in records:
            s = SPLIT_IDS.get(r.get("split", "train"), 0)
            split_counts[s] = split_counts.get(s, 0) + 1
        dominant_split = max(split_counts, key=split_counts.get)
        
        # Sérialiser
        raw_parts = []
        for record in records:
            record_bytes = json.dumps(record, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            raw_parts.append(struct.pack("<I", len(record_bytes)))
            raw_parts.append(record_bytes)
        
        block_header = MAGIC_BLOCK + struct.pack("<I", block_idx)
        uncompressed = block_header + b"".join(raw_parts)
        compressed = self._compressor.compress(uncompressed)
        
        meta = {
            "compressed_size": len(compressed),
            "uncompressed_size": len(uncompressed),
            "n_records": len(records),
            "split_id": dominant_split,
        }
        
        return compressed, meta, uncompressed

    def _write_patch(
        self,
        output_path: Path,
        source_crc64: int,
        blocks: List[bytes],
        block_meta: List[Dict],
        crc_data: bytes,
        n_records: int,
        metadata: Dict[str, Any],
    ) -> int:
        """Écrit le fichier patch sur disque."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Calculer le CRC des nouveaux blocs
        new_crc = crc64(crc_data)
        
        with open(output_path, "wb") as f:
            # Header (32 bytes)
            # [4] magic PTCH
            # [8] source_crc64
            # [8] created_at timestamp
            # [4] n_records
            # [4] n_blocks
            # [4] reserved
            header = (
                MAGIC_PATCH_HEADER +           # 4 bytes
                struct.pack("<Q", source_crc64) +  # 8 bytes
                struct.pack("<Q", int(time.time())) +  # 8 bytes
                struct.pack("<I", n_records) +  # 4 bytes
                struct.pack("<I", len(blocks)) +  # 4 bytes
                b"\x00" * 4  # 4 bytes reserved = 32 total
            )
            assert len(header) == PATCH_HEADER_SIZE, f"Header size mismatch: {len(header)}"
            f.write(header)
            
            # Index des blocs (même format que .loop)
            blocks_start = PATCH_HEADER_SIZE + len(blocks) * INDEX_ENTRY_SIZE
            cursor = blocks_start
            
            for i, meta in enumerate(block_meta):
                entry = (
                    struct.pack("<Q", cursor) +
                    struct.pack("<I", meta["compressed_size"]) +
                    struct.pack("<I", meta["uncompressed_size"]) +
                    struct.pack("<I", meta["n_records"]) +
                    struct.pack("<H", meta["split_id"]) +
                    struct.pack("<H", 0)  # reserved
                )
                f.write(entry)
                cursor += meta["compressed_size"]
            
            # Blocs de données
            for block in blocks:
                f.write(block)
            
            # Métadonnées
            meta_json = json.dumps({
                **metadata,
                "patch_format_version": "1.0",
                "n_new_records": n_records,
                "n_new_blocks": len(blocks),
                "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source_crc64": f"{source_crc64:016x}",
                "new_crc64": f"{new_crc:016x}",
            }, ensure_ascii=False, separators=(",", ":"))
            meta_bytes = self._compressor.compress(meta_json.encode("utf-8"))
            
            f.write(meta_bytes)
            
            # Footer (8 bytes)
            footer = (
                struct.pack("<I", len(meta_bytes)) +
                MAGIC_PATCH_FOOTER
            )
            assert len(footer) == PATCH_FOOTER_SIZE
            f.write(footer)
        
        size = output_path.stat().st_size
        logger.info(
            f"Patch créé : {output_path} — {n_records} records, "
            f"{len(blocks)} blocs, {size / 1024:.1f} KB"
        )
        return size

    def _read_patch(self, patch_path: Path) -> Dict[str, Any]:
        """Lit et parse un fichier patch."""
        with open(patch_path, "rb") as f:
            # Header
            raw_header = f.read(PATCH_HEADER_SIZE)
            if len(raw_header) < PATCH_HEADER_SIZE:
                raise PatchError("Fichier patch trop petit")
            
            magic = raw_header[:4]
            if magic != MAGIC_PATCH_HEADER:
                raise PatchError(f"Magic header invalide : {magic!r}")
            
            source_crc64 = struct.unpack("<Q", raw_header[4:12])[0]
            created_at = struct.unpack("<Q", raw_header[12:20])[0]
            n_records = struct.unpack("<I", raw_header[20:24])[0]
            n_blocks = struct.unpack("<I", raw_header[24:28])[0]
            
            # Lire l'index
            index = []
            for _ in range(n_blocks):
                raw = f.read(INDEX_ENTRY_SIZE)
                if len(raw) < INDEX_ENTRY_SIZE:
                    raise PatchError("Index tronqué")
                
                offset, comp_size, uncomp_size, n_rec, split_id, _ = struct.unpack(
                    "<QIIIHH", raw
                )
                index.append({
                    "offset": offset,
                    "compressed_size": comp_size,
                    "uncompressed_size": uncomp_size,
                    "n_records": n_rec,
                    "split_id": split_id,
                })
            
            # Lire les blocs (on les garde en mémoire pour la fusion)
            blocks_data = []
            for entry in index:
                f.seek(entry["offset"])
                compressed = f.read(entry["compressed_size"])
                blocks_data.append(compressed)
            
            # Lire le footer pour trouver les métadonnées
            f.seek(-PATCH_FOOTER_SIZE, 2)
            raw_footer = f.read(PATCH_FOOTER_SIZE)
            
            magic_end = raw_footer[4:]
            if magic_end != MAGIC_PATCH_FOOTER:
                raise PatchError(f"Magic footer invalide : {magic_end!r}")
            
            meta_compressed_size = struct.unpack("<I", raw_footer[:4])[0]
            
            # Lire les métadonnées
            meta_offset = patch_path.stat().st_size - PATCH_FOOTER_SIZE - meta_compressed_size
            f.seek(meta_offset)
            compressed_meta = f.read(meta_compressed_size)
            
            decompressor = zstd.ZstdDecompressor()
            raw_meta = decompressor.decompress(compressed_meta)
            metadata = json.loads(raw_meta.decode("utf-8"))
            
            return {
                "source_crc64": source_crc64,
                "created_at": created_at,
                "n_records": n_records,
                "n_blocks": n_blocks,
                "index": index,
                "blocks_data": blocks_data,
                "metadata": metadata,
            }

    def _merge(
        self, 
        base_reader: LoopReader, 
        patch_data: Dict[str, Any], 
        output_path: Path
    ) -> int:
        """Fusionne le fichier de base avec le patch."""
        # Collecter tous les records du fichier de base
        base_records = list(base_reader.stream())
        
        # Collecter les records du patch
        decompressor = zstd.ZstdDecompressor()
        patch_records = []
        
        for block_data in patch_data["blocks_data"]:
            raw = decompressor.decompress(block_data)
            
            # Vérifier magic du bloc
            if raw[:4] != MAGIC_BLOCK:
                raise PatchError("Bloc de patch corrompu (magic invalide)")
            
            # Sauter block_magic + block_index
            pos = 8
            
            while pos < len(raw):
                if pos + 4 > len(raw):
                    break
                
                record_len = struct.unpack("<I", raw[pos:pos+4])[0]
                pos += 4
                
                if record_len == 0 or pos + record_len > len(raw):
                    break
                
                record_bytes = raw[pos:pos+record_len]
                pos += record_len
                
                try:
                    record = json.loads(record_bytes.decode("utf-8"))
                    patch_records.append(record)
                except json.JSONDecodeError as e:
                    logger.warning(f"Record JSON invalide dans le patch : {e}")
        
        # Fusionner les métadonnées
        base_meta = base_reader.metadata
        patch_meta = patch_data["metadata"]
        
        merged_metadata = {
            **base_meta,
            "name": base_meta.get("name", "") + "_patched",
            "description": f"{base_meta.get('description', '')} + patch ({patch_data['n_records']} records)",
            "patched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "patch_source_crc": patch_meta.get("source_crc64"),
        }
        
        # Créer le fichier fusionné
        writer = LoopWriter(output_path, metadata=merged_metadata)
        writer.add_many(base_records)
        writer.add_many(patch_records)
        
        return writer.save()


def cmd_patch_create(args) -> None:
    """Commande CLI pour créer un patch."""
    from looplib.cli import _progress_context
    
    try:
        size = LoopPatcher.create(
            args.base,
            args.records,
            args.output,
            metadata=getattr(args, 'metadata', None),
        )
        print(f"\n  ✓ Patch créé : {args.output}")
        print(f"  ✓ Taille     : {size / 1024:.1f} KB\n")
    except PatchError as e:
        print(f"\n  ✗ Erreur : {e}\n")
        raise SystemExit(1)


def cmd_patch_apply(args) -> None:
    """Commande CLI pour appliquer un patch."""
    try:
        size = LoopPatcher.apply(args.base, args.patch, args.output)
        print(f"\n  ✓ Patch appliqué : {args.output}")
        print(f"  ✓ Taille fusionnée : {size / 1024:.1f} KB\n")
    except PatchError as e:
        print(f"\n  ✗ Erreur : {e}\n")
        raise SystemExit(1)
