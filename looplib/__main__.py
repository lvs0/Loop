"""
looplib — Bibliothèque Python officielle du format .loop
SOE Project · https://github.com/lvs0

Format natif pour le fine-tuning de LLMs :
  - Binaire columnar, compressé Zstd par bloc
  - Conversation-native (system/user/assistant)
  - Sequence packing intégré
  - Streaming random-access via index binaire
  - Qualité par record, filtre à la lecture
  - Self-describing, intégrité CRC64
"""

from looplib.writer import LoopWriter
from looplib.streaming import StreamingLoopWriter
from looplib.reader import LoopReader
from looplib.validator import LoopValidator, ValidationError
from looplib.packer import SequencePacker
from looplib.patcher import LoopPatcher, PatchError
from looplib.utils import crc64, schema_hash, format_bytes

__version__ = "1.0.4"
__format_version__ = (1, 0)
__all__ = [
    "LoopWriter",
    "StreamingLoopWriter", 
    "LoopReader",
    "LoopValidator",
    "SequencePacker",
    "LoopPatcher",
    "ValidationError",
    "PatchError",
    "crc64",
    "schema_hash",
    "format_bytes",
]


def main():
    """Entry point for python -m looplib"""
    from looplib.cli import main as cli_main
    cli_main()


if __name__ == "__main__":
    main()
