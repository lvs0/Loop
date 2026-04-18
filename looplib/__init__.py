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
from looplib.reader import LoopReader
from looplib.validator import LoopValidator, ValidationError
from looplib.packer import SequencePacker

__version__ = "1.0.0"
__format_version__ = (1, 0)
__all__ = ["LoopWriter", "LoopReader", "LoopValidator", "SequencePacker", "ValidationError"]
