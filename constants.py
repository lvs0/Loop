"""Constantes du format .loop v1.0"""

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
COMPRESSION_NONE = 0
COMPRESSION_ZSTD = 1
