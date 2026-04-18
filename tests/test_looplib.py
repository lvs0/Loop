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
        self.v.validate(SAMPLE_RECORD)

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
        record = {
            "messages": [
                {"role": "system",    "content": "Système."},
                {"role": "user",      "content": "Question."},
                {"role": "assistant", "content": "Réponse."},
                {"role": "tool",      "content": "Résultat outil."},
            ]
        }
        self.v.validate(record)


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
        assert result is w

    def test_add_many(self, tmp_path):
        path = tmp_path / "many.loop"
        w = LoopWriter(path)
        w.add_many(SAMPLE_RECORDS[:10])
        w.save()
        assert path.exists()

    def test_block_flush(self, tmp_path):
        path   = tmp_path / "blocks.loop"
        w      = LoopWriter(path, block_size=5)
        n      = 23
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
        assert len(records) == 10

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

        with open(output_path) as f:
            lines = [json.loads(l) for l in f if l.strip()]
        assert len(lines) == len(SAMPLE_RECORDS)

    def test_corrupt_magic_raises(self, tmp_path):
        from looplib.reader import LoopParseError
        path = tmp_path / "corrupt.loop"
        path.write_bytes(b"FAKE" + b"\x00" * 100)

        with pytest.raises(LoopParseError, match="Magic"):
            LoopReader(path)

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            LoopReader(tmp_path / "nonexistent.loop")

    def test_to_huggingface_uses_generator(self, tmp_loop):
        pytest.importorskip("datasets")
        from datasets import Dataset
        from looplib.reader import LoopReader

        reader = LoopReader(tmp_loop)
        ds = reader.to_huggingface()

        assert isinstance(ds, Dataset)
        assert len(ds) == len(SAMPLE_RECORDS)


# ──────────────────────────────────────────────────────────────────────────────
# Tests SequencePacker
# ──────────────────────────────────────────────────────────────────────────────

class TestSequencePacker:

    @pytest.fixture
    def fake_tokenizer(self):
        """Un tokenizer minimal qui produit ~3-5 tokens par mot (avec special tokens)."""
        class FakeTokenizer:
            def __init__(self):
                self.eos_token_id = 2
                self.pad_token_id = 0

            def encode(self, text, add_special_tokens=True):
                words = text.strip().split() or [""]
                # Chaque "mot" dans le texte devient 1 token
                ids = [abs(hash(w)) % 200 for w in text.split()] or [abs(hash(text)) % 200]
                if add_special_tokens:
                    ids = [1] + ids + [2]
                return ids

            def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False):
                parts = []
                for m in messages:
                    parts.append(f"<|{m['role']}|>{m['content']}")
                text = "".join(parts)
                if add_generation_prompt:
                    text += "<|assistant|>"
                return text

        return FakeTokenizer()

    def test_packer_produces_correct_seq_len(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        # With max_seq_len=128 and short Q0/A0 messages (~5-8 tokens), packing should work
        packer = SequencePacker(fake_tokenizer, max_seq_len=128)
        records = [
            {"messages": [{"role": "user", "content": f"Q{i}"}, {"role": "assistant", "content": f"A{i}"}]}
            for i in range(20)
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) > 0, "Packer should produce sequences"
        for seq in seqs:
            assert len(seq["input_ids"]) == 128
            assert len(seq["labels"]) == 128
            assert len(seq["attention_mask"]) == 128
            assert len(seq["position_ids"]) == 128

    def test_packer_eos_between_conversations(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=128, add_eos_between=True)
        records = [
            {"messages": [{"role": "user", "content": "Short question"}, {"role": "assistant", "content": "Short answer"}]}
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) == 1, "Should produce exactly one packed sequence"
        seq = seqs[0]
        assert seq["input_ids"].count(2) >= 1, "EOS token (2) should appear"

    def test_packer_no_eos_between(self, fake_tokenizer):
        """With add_eos_between=False, no extra EOS separator is added between conversations.
        Each conversation still ends with its own EOS token."""
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=128, add_eos_between=False)
        # 3 short conversations that can all fit in one packed sequence
        records = [
            {"messages": [{"role": "user", "content": f"Q{i}"}, {"role": "assistant", "content": f"A{i}"}]}
            for i in range(3)
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) > 0
        seq = seqs[0]
        content_ids = [x for x in seq["input_ids"] if x != 0]
        # With add_eos_between=False, only conversation-final EOS tokens appear
        # No extra separator EOS is inserted between conversations
        eos_positions = [i for i, x in enumerate(content_ids) if x == 2]
        assert len(eos_positions) == 3, f"Expected 3 EOS (one per conv), got {len(eos_positions)}"

    def test_packer_ignores_too_long_conversation(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=8, add_eos_between=False)
        records = [
            {"messages": [{"role": "user", "content": "word " * 20}, {"role": "assistant", "content": "answer"}]}
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) == 0, "Too-long conversation should be ignored"

    def test_packer_labels_mask_non_assistant(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=128, label_ignore_id=-100)
        records = [
            {"messages": [
                {"role": "system", "content": "Be helpful"},
                {"role": "user", "content": "Hello"},
                {"role": "assistant", "content": "Hi there"},
            ]}
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) > 0
        labels = seqs[0]["labels"]
        assert -100 in labels, "Non-assistant tokens should be masked"

    def test_packer_position_ids_reset_per_conversation(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=128, add_eos_between=True)
        records = [
            {"messages": [{"role": "user", "content": f"Q{i}"}, {"role": "assistant", "content": f"A{i}"}]}
            for i in range(3)
        ]
        seqs = list(packer.pack(iter(records)))
        assert len(seqs) > 0
        pos_ids = seqs[0]["position_ids"]
        assert len(set(pos_ids)) > 1, "Position IDs should have multiple values"

    def test_packer_efficiency(self, fake_tokenizer):
        from looplib.packer import SequencePacker
        packer = SequencePacker(fake_tokenizer, max_seq_len=128)
        records = [
            {"messages": [{"role": "user", "content": f"Q{i}"}, {"role": "assistant", "content": f"A{i}"}]}
            for i in range(10)
        ]
        stats = packer.efficiency(iter(records))
        assert "naive_gpu_usage" in stats
        assert "packed_gpu_usage" in stats
        assert "speedup_factor" in stats
        # naive usage should be a valid percentage
        assert 0 < stats["naive_gpu_usage"] <= 100
        # packed usage capped at ~100%
        assert 0 < stats["packed_gpu_usage"] <= 100
        # Packing should give meaningfully better GPU utilization than naive
        assert stats["packed_gpu_usage"] > stats["naive_gpu_usage"], \
            f"Packing should improve GPU usage: naive={stats['naive_gpu_usage']}, packed={stats['packed_gpu_usage']}"


# ──────────────────────────────────────────────────────────────────────────────
# Tests intégrité
# ──────────────────────────────────────────────────────────────────────────────

class TestIntegrity:

    def test_messages_preserved(self, tmp_path):
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
