"""
LoopValidator — Validation des records .loop

Vérifie qu'un record respecte le schéma avant d'être écrit.
"""

from typing import Dict, Any
from looplib.constants import VALID_ROLES


class ValidationError(Exception):
    """Erreur de validation d'un record .loop."""
    pass


class LoopValidator:
    """Valide les records avant écriture."""

    def validate(self, record: Dict[str, Any]) -> None:
        """
        Valide un record. Lève ValidationError si invalide.

        Args:
            record: Le record à valider.

        Raises:
            ValidationError: Si le record est invalide.
        """
        if not isinstance(record, dict):
            raise ValidationError(f"Un record doit être un dict, reçu : {type(record).__name__}")

        # messages obligatoire
        if "messages" not in record:
            raise ValidationError("Champ obligatoire manquant : 'messages'")

        messages = record["messages"]
        if not isinstance(messages, list) or len(messages) == 0:
            raise ValidationError("'messages' doit être une liste non vide")

        has_user      = False
        has_assistant = False

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                raise ValidationError(f"messages[{i}] doit être un dict")
            if "role" not in msg:
                raise ValidationError(f"messages[{i}] : champ 'role' manquant")
            if "content" not in msg:
                raise ValidationError(f"messages[{i}] : champ 'content' manquant")

            role = msg["role"]
            if role not in VALID_ROLES:
                raise ValidationError(
                    f"messages[{i}] : role '{role}' invalide. "
                    f"Valeurs acceptées : {sorted(VALID_ROLES)}"
                )
            if not isinstance(msg["content"], str) or not msg["content"].strip():
                raise ValidationError(
                    f"messages[{i}] : 'content' doit être une chaîne non vide"
                )

            if role == "user":
                has_user = True
            elif role == "assistant":
                has_assistant = True

        if not has_user:
            raise ValidationError("Un record doit contenir au moins un message 'user'")
        if not has_assistant:
            raise ValidationError("Un record doit contenir au moins un message 'assistant'")

        # Champs optionnels
        if "quality" in record:
            q = record["quality"]
            if not isinstance(q, (int, float)) or not (0.0 <= float(q) <= 1.0):
                raise ValidationError(f"'quality' doit être un float entre 0.0 et 1.0, reçu : {q}")

        if "tokens" in record:
            t = record["tokens"]
            if not isinstance(t, int) or t <= 0:
                raise ValidationError(f"'tokens' doit être un entier positif, reçu : {t}")

        if "language" in record:
            lang = record["language"]
            if not isinstance(lang, str) or len(lang) != 2:
                raise ValidationError(
                    f"'language' doit être un code ISO 639-1 à 2 lettres (ex: 'fr'), reçu : {lang!r}"
                )

        if "split" in record:
            split = record["split"]
            valid_splits = {"train", "val", "test", "all"}
            if split not in valid_splits:
                raise ValidationError(
                    f"'split' invalide : {split!r}. Valeurs acceptées : {sorted(valid_splits)}"
                )

        if "tags" in record:
            tags = record["tags"]
            if not isinstance(tags, list):
                raise ValidationError("'tags' doit être une liste")
            for tag in tags:
                if not isinstance(tag, str):
                    raise ValidationError(f"Chaque tag doit être une chaîne, reçu : {type(tag).__name__}")

    def __enter__(self) -> "LoopValidator":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        pass
