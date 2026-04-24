"""
Utilitaires partagés pour looplib.

Fonctions communes utilisées par plusieurs modules pour éviter la duplication.
"""

from __future__ import annotations

import json
import struct
import hashlib
from typing import Dict, Any

from looplib.constants import CRC64_TABLE


def crc64(data: bytes) -> int:
    """
    Calcule le CRC64/ECMA-182 d'un bloc de données.
    
    Utilise une table de lookup précalculée pour des performances optimales.
    Cette fonction est thread-safe et peut être utilisée en parallèle.
    
    Args:
        data: Bloc de données à hasher.
        
    Returns:
        Valeur CRC64 sur 64 bits.
        
    Example:
        >>> crc64(b"hello world")
        2857494483891625019
    """
    crc = 0xFFFFFFFFFFFFFFFF
    for byte in data:
        crc = CRC64_TABLE[(crc ^ byte) & 0xFF] ^ (crc >> 8)
    return crc ^ 0xFFFFFFFFFFFFFFFF


def schema_hash(schema: dict) -> int:
    """
    Calcule un hash MD5 tronqué à 4 bytes du schéma.
    
    Utilisé pour détecter les incompatibilités de schéma entre versions.
    Le schéma est sérialisé en JSON avec clés triées pour garantir
    la stabilité du hash.
    
    Args:
        schema: Dictionnaire du schéma à hasher.
        
    Returns:
        Hash sur 32 bits (4 bytes) du schéma.
    """
    raw = json.dumps(schema, sort_keys=True).encode("utf-8")
    md5 = hashlib.md5(raw).digest()
    return struct.unpack("<I", md5[:4])[0]


def format_bytes(size_bytes: int) -> str:
    """
    Formate une taille en bytes en unités lisibles (KB, MB, GB).
    
    Args:
        size_bytes: Taille en bytes.
        
    Returns:
        Chaîne formatée avec l'unité appropriée.
        
    Example:
        >>> format_bytes(1536000)
        '1.46 MB'
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"


def clamp(value: float, min_val: float, max_val: float) -> float:
    """
    Restreint une valeur à un intervalle [min_val, max_val].
    
    Args:
        value: Valeur à restreindre.
        min_val: Borne inférieure.
        max_val: Borne supérieure.
        
    Returns:
        Valeur restreinte.
    """
    return max(min_val, min(max_val, value))


def calculate_percentile(sorted_values: list[float], percentile: float) -> float:
    """
    Calcule un percentile sur une liste de valeurs triées.
    
    Args:
        sorted_values: Liste de valeurs déjà triées (croissant).
        percentile: Percentile à calculer (0.0 à 1.0).
        
    Returns:
        Valeur au percentile demandé.
        
    Example:
        >>> calculate_percentile([1, 2, 3, 4, 5], 0.5)
        3.0
    """
    if not sorted_values:
        return 0.0
    n = len(sorted_values)
    index = int(n * percentile)
    index = max(0, min(index, n - 1))
    return sorted_values[index]
