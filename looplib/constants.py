"""Constantes du format .loop v1.0"""

from typing import Final

__all__ = [
    "MAGIC_HEADER",
    "MAGIC_FOOTER",
    "MAGIC_BLOCK",
    "HEADER_SIZE",
    "INDEX_ENTRY_SIZE",
    "FOOTER_SIZE",
    "FORMAT_VERSION_MAJOR",
    "FORMAT_VERSION_MINOR",
    "FLAG_COMPRESSION_ZSTD",
    "FLAG_HAS_PRETOKENIZED",
    "FLAG_HAS_QUALITY_INDEX",
    "FLAG_MULTI_SPLIT",
    "SPLIT_TRAIN",
    "SPLIT_VAL",
    "SPLIT_TEST",
    "SPLIT_ALL",
    "SPLIT_NAMES",
    "SPLIT_IDS",
    "VALID_ROLES",
    "MAX_RECORD_SIZE",
    "MAX_BLOCK_SIZE",
    "ZSTD_LEVEL",
    "COMPRESSION_NONE",
    "COMPRESSION_ZSTD",
    "CRC64_POLYNOMIAL",
    "CRC64_TABLE",
]

# Magic bytes
MAGIC_HEADER  = b"LOOP"           # début de fichier
MAGIC_FOOTER  = b"POOL"           # fin de fichier (LOOP inversé)
MAGIC_BLOCK   = b"BLOK"           # début de chaque bloc de données

# Tailles fixes
HEADER_SIZE   = 64                # bytes
INDEX_ENTRY_SIZE = 24             # bytes par entrée d'index
FOOTER_SIZE   = 16                # bytes

# Version du format
FORMAT_VERSION_MAJOR = 1
FORMAT_VERSION_MINOR = 0

# FLAGS (bits dans le uint16 FLAGS du header)
FLAG_COMPRESSION_ZSTD    = 1 << 0
FLAG_HAS_PRETOKENIZED    = 1 << 1
FLAG_HAS_QUALITY_INDEX   = 1 << 2
FLAG_MULTI_SPLIT         = 1 << 3

# Splits
SPLIT_TRAIN = 0
SPLIT_VAL   = 1
SPLIT_TEST  = 2
SPLIT_ALL   = 3

SPLIT_NAMES = {SPLIT_TRAIN: "train", SPLIT_VAL: "val", SPLIT_TEST: "test", SPLIT_ALL: "all"}
SPLIT_IDS   = {"train": SPLIT_TRAIN, "val": SPLIT_VAL, "test": SPLIT_TEST, "all": SPLIT_ALL}

# Roles valides pour les messages
VALID_ROLES = {"system", "user", "assistant", "tool", "function"}

# Limites de sécurité
MAX_RECORD_SIZE   = 1_048_576    # 1MB par record max
MAX_BLOCK_SIZE    = 512          # records par bloc par défaut
ZSTD_LEVEL        = 9            # niveau de compression (1-22)

# Compression
COMPRESSION_NONE: Final[int] = 0
COMPRESSION_ZSTD: Final[int] = 1

# CRC64 constants for efficient checksum computation
CRC64_POLYNOMIAL: Final[int] = 0xC96C5795D7870F42


def _build_crc64_table() -> list[int]:
    """Build CRC64 lookup table once at module load time."""
    table = []
    for i in range(256):
        crc = i
        for _ in range(8):
            crc = (crc >> 1) ^ (CRC64_POLYNOMIAL if crc & 1 else 0)
        table.append(crc)
    return table


CRC64_TABLE: Final[list[int]] = _build_crc64_table()
