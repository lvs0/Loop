"""
tests/test_looplib.py — Tests unitaires de looplib

Lance avec : pytest tests/ -v
"""

import json
import struct
import tempfile
from pathlib import Path

import pytest

from looplib import LoopWriter, LoopReader, LoopValidator, ValidationError
from looplib.constants import MAGIC_HEADER, MAGIC_FOOTER, HEADER_SIZE, FOOTER_SIZE


# ──────────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────────

SAMPLE_RECORD = {
    "messages": [
        {"role": "system",    "content": "Tu es un expert Python."},
        {"role": "user",      "content": "Comment lire un fichier CSV ?"},
        {"role": "assistant", "content": "Utilise pandas.read_csv() pour lire facilement un CSV."},
    ],
    "quality":  0.82,
    "language": "fr",
    "tags":     ["python", "csv", "pandas"],
    "split":    "train",
    "tokens":   42,
}

SAMPLE_RECORDS = [
    {
        "messages": [
            {"role": "user",      "content": f"Question {i} ?"},
            {"role": "assistant", "content": f"Réponse {i}."},
        ],
        "quality": 0.6 + (i % 4) * 0.1,
        "split":   "train" if i % 5 != 0 else "val",
        "tokens":  20 + i,
    }
    for i in range(50)
]


@pytest.fixture
def tmp_loop(tmp_path):
    """Crée un fichier .loop temporaire avec SAMPLE_RECORDS."""
    path = tmp_path / "test.loop"
    writer = LoopWriter(path, metadata={"name": "test_dataset", "category": "test", "language": "fr"})
    writer.add_many(SAMPLE_RECORDS)
    writer.save()
    return path


# ──────────────────────────────────────────────────────────────────────────────
# Tests Validator
# ──────────────────────────────────────────────────────────────────────────────

class TestLoopValidator:

    def setup_method(self):
        self.v = LoopValidator()

    def test_valid_record(self):
        self.v.validate(SAMPLE_RECORD)  # Ne doit pas lever d'exception

    def test_missing_messages(self):
        with pytest.raises(ValidationError, match="messages"):
            self.v.validate({"quality": 0.8})

    def test_empty_messages(self):
        with pytest.raises(ValidationError):
            self.v.validate({"messages": []})

    def test_missing_user(self):
        with pytest.raises(ValidationError, match="user"):
            self.v.validate({"messages": [
                {"role": "assistant", "content": "Réponse."}
            ]})

    def test_missing_assistant(self):
        with pytest.raises(ValidationError, match="assistant"):
            self.v.validate({"messages": [
                {"role": "user", "content": "Question ?"}
            ]})

    def test_invalid_role(self):
        with pytest.raises(ValidationError, match="role"):
            self.v.validate({"messages": [
                {"role": "robot",     "content": "Beep."},
                {"role": "assistant", "content": "Réponse."},
            ]})

    def test_empty_content(self):
        with pytest.raises(ValidationError, match="content"):
            self.v.validate({"messages": [
                {"role": "user",      "content": ""},
                {"role": "assistant", "content": "Réponse."},
            ]})

    def test_quality_out_of_range(self):
        with pytest.raises(ValidationError, match="quality"):
            self.v.validate({**SAMPLE_RECORD, "quality": 1.5})

    def test_quality_negative(self):
        with pytest.raises(ValidationError, match="quality"):
            self.v.validate({**SAMPLE_RECORD, "quality": -0.1})

    def test_invalid_language_code(self):
        with pytest.raises(ValidationError, match="language"):
            self.v.validate({**SAMPLE_RECORD, "language": "fra"})

    def test_invalid_split(self):
        with pytest.raises(ValidationError, match="split"):
            self.v.validate({**SAMPLE_RECORD, "split": "unknown"})

    def test_valid_all_roles(self):
        """Tous les roles valides doivent passer si user+assistant présents."""
        record = {
            "messages": [
                {"role": "system",    "content": "Système."},
                {"role": "user",      "content": "Question."},
                {"role": "assistant", "content": "Réponse."},
                {"role": "tool",      "content": "Résultat outil."},
            ]
        }
        self.v.validate(record)  # Ne doit pas lever


# ──────────────────────────────────────────────────────────────────────────────
# Tests Writer
# ──────────────────────────────────────────────────────────────────────────────

class TestLoopWriter:

    def test_creates_file(self, tmp_path):
        path = tmp_path / "out.loop"
        w = LoopWriter(path)
        w.add(SAMPLE_RECORD)
        w.save()
        assert path.exists()
        assert path.stat().st_size > 0

    def test_magic_bytes(self, tmp_path):
        path = tmp_path / "out.loop"
        w = LoopWriter(path)
        w.add(SAMPLE_RECORD)
        w.save()

        with open(path, "rb") as f:
            header_magic = f.read(4)
            f.seek(-4, 2)
            footer_magic = f.read(4)

        assert header_magic == MAGIC_HEADER
        assert footer_magic == MAGIC_FOOTER

    def test_header_size(self, tmp_path):
        path = tmp_path / "out.loop"
        w = LoopWriter(path)
        w.add(SAMPLE_RECORD)
        w.save()
        assert path.stat().st_size >= HEADER_SIZE + FOOTER_SIZE

    def test_save_empty_raises(self, tmp_path):
        path = tmp_path / "empty.loop"
        w = LoopWriter(path)
        with pytest.raises(ValueError, match="vide"):
            w.save()

    def test_chainable_add(self, tmp_path):
        path = tmp_path / "chain.loop"
        w = LoopWriter(path)
        result = w.add(SAMPLE_RECORD)
        assert result is w  # Doit retourner self

    def test_add_many(self, tmp_path):
        path = tmp_path / "many.loop"
        w = LoopWriter(path)
        w.add_many(SAMPLE_RECORDS[:10])
        w.save()
        assert path.exists()

    def test_block_flush(self, tmp_path):
        """Vérifie que les blocs sont créés correctement avec block_size petit."""
        path   = tmp_path / "blocks.loop"
        w      = LoopWriter(path, block_size=5)
        n      = 23  # Doit créer ceil(23/5) = 5 blocs
        for i in range(n):
            r = {
                "messages": [
                    {"role": "user",      "content": f"Q{i}"},
                    {"role": "assistant", "content": f"A{i}"},
                ]
            }
            w.add(r)
        w.save()
        reader = LoopReader(path)
        assert reader._header["n_blocks"] == 5
        assert reader._header["n_records"] == n

    def test_metadata_embedded(self, tmp_path):
        path = tmp_path / "meta.loop"
        w = LoopWriter(path, metadata={"name": "mon_test", "category": "code", "language": "fr"})
        w.add(SAMPLE_RECORD)
        w.save()

        reader = LoopReader(path)
        assert reader.metadata["name"]     == "mon_test"
        assert reader.metadata["category"] == "code"
        assert reader.metadata["language"] == "fr"


# ──────────────────────────────────────────────────────────────────────────────
# Tests Reader
# ──────────────────────────────────────────────────────────────────────────────

class TestLoopReader:

    def test_round_trip(self, tmp_loop):
        """Écrire puis relire doit donner les mêmes records."""
        reader  = LoopReader(tmp_loop)
        records = reader.to_list()
        assert len(records) == len(SAMPLE_RECORDS)

    def test_n_records_matches_header(self, tmp_loop):
        reader = LoopReader(tmp_loop)
        assert reader._header["n_records"] == len(SAMPLE_RECORDS)

    def test_stream_min_quality(self, tmp_loop):
        reader  = LoopReader(tmp_loop)
        records = list(reader.stream(min_quality=0.80))
        assert all(r.get("quality", 1.0) >= 0.80 for r in records)
        assert len(records) < len(SAMPLE_RECORDS)

    def test_stream_max_quality(self, tmp_loop):
        reader  = LoopReader(tmp_loop)
        records = list(reader.stream(max_quality=0.70))
        assert all(r.get("quality", 0.0) <= 0.70 for r in records)

    def test_stream_split_train(self, tmp_loop):
        reader  = LoopReader(tmp_loop)
        records = list(reader.stream(split="train"))
        assert all(r.get("split", "train") == "train" for r in records)

    def test_stream_split_val(self, tmp_loop):
        reader  = LoopReader(tmp_loop)
        records = list(reader.stream(split="val"))
        assert all(r.get("split") == "val" for r in records)
        assert len(records) == 10  # 1 sur 5 → indices 0,5,10,15,20,25,30,35,40,45

    def test_read_block_direct(self, tmp_loop):
        reader  = LoopReader(tmp_loop)
        block_0 = reader.read_block(0)
        assert len(block_0) > 0
        assert all("messages" in r for r in block_0)

    def test_read_block_out_of_range(self, tmp_loop):
        reader = LoopReader(tmp_loop)
        with pytest.raises(IndexError):
            reader.read_block(reader._header["n_blocks"] + 1)

    def test_count_no_filter(self, tmp_loop):
        reader = LoopReader(tmp_loop)
        assert reader.count() == len(SAMPLE_RECORDS)

    def test_info_returns_dict(self, tmp_loop):
        reader = LoopReader(tmp_loop)
        info   = reader.info()
        assert isinstance(info, dict)
        assert "n_records" in info
        assert "file_size_mb" in info

    def test_to_jsonl(self, tmp_loop, tmp_path):
        reader      = LoopReader(tmp_loop)
        output_path = tmp_path / "output.jsonl"
        count       = reader.to_jsonl(output_path)

        assert count == len(SAMPLE_RECORDS)
        assert output_path.exists()

        # Vérifier que le JSONL est valide
        with open(output_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert len(lines) == len(SAMPLE_RECORDS)

    def test_corrupt_magic_raises(self, tmp_path):
        """Un fichier avec magic invalide doit lever LoopParseError."""
        from looplib.reader import LoopParseError
        path = tmp_path / "corrupt.loop"
        path.write_bytes(b"FAKE" + b"\x00" * 100)

        with pytest.raises(LoopParseError, match="Magic"):
            LoopReader(path)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            LoopReader(tmp_path / "nonexistent.loop")

    def test_to_huggingface_uses_generator(self, tmp_loop):
        """to_huggingface() doit utiliser from_generator (streaming, pas to_list)."""
        pytest.importorskip("datasets")
        from datasets import Dataset
        from looplib.reader import LoopReader

        reader = LoopReader(tmp_loop)
        ds = reader.to_huggingface()

        # Vérifie que c'est un Dataset HuggingFace
        assert isinstance(ds, Dataset)
        # Vérifie que les records sont bien présents
        assert len(ds) == len(SAMPLE_RECORDS)


# ──────────────────────────────────────────────────────────────────────────────
# Tests intégrité
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegrity:

    def test_messages_preserved(self, tmp_path):
        """Les messages doivent être identiques après écriture/lecture."""
        path = tmp_path / "integrity.loop"
        original = {
            "messages": [
                {"role": "system",    "content": "Contexte spécial."},
                {"role": "user",      "content": "Question avec 'guillemets' et \"doubles\"."},
                {"role": "assistant", "content": "Réponse avec émojis 🚀 et accents éàü."},
            ],
            "quality": 0.95,
            "language": "fr",
        }

        writer = LoopWriter(path)
        writer.add(original)
        writer.save()

        reader  = LoopReader(path)
        records = reader.to_list()
        assert len(records) == 1

        result = records[0]
        assert len(result["messages"]) == 3
        assert result["messages"][0]["role"]    == "system"
        assert result["messages"][2]["content"] == "Réponse avec émojis 🚀 et accents éàü."
        assert result["quality"]                == 0.95

    def test_large_dataset(self, tmp_path):
        """Teste avec 1000 records pour vérifier la robustesse."""
        path = tmp_path / "large.loop"
        n    = 1000

        writer = LoopWriter(path, block_size=100)
        for i in range(n):
            writer.add({
                "messages": [
                    {"role": "user",      "content": f"Question numéro {i}"},
                    {"role": "assistant", "content": f"Réponse numéro {i}, plus longue."},
                ],
                "quality": round(0.5 + (i % 50) / 100, 2),
                "tokens":  15 + (i % 30),
            })
        writer.save()

        reader = LoopReader(path)
        assert reader._header["n_records"] == n

        count = sum(1 for _ in reader.stream())
        assert count == n
