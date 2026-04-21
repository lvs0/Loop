"""
tests/test_looplib.py — Tests unitaires de looplib

Lance avec : pytest tests/ -v
"""

import json
import struct
import tempfile
from pathlib import Path

import pytest

from looplib import LoopWriter, StreamingLoopWriter, LoopReader, LoopValidator, ValidationError
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

    def test_stream_language_filter(self, tmp_path):
        """Language filter: records without a language field must NOT pass the filter."""
        path = tmp_path / "lang.loop"
        w    = LoopWriter(path, metadata={"name": "lang_test", "category": "test", "language": "fr"})
        w.add({"messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}], "language": "fr", "split": "train"})
        w.add({"messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}], "language": "en", "split": "train"})
        w.add({"messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]})  # no language
        w.save()

        reader = LoopReader(path)
        assert len(list(reader.stream(language="fr"))) == 1
        assert len(list(reader.stream(language="en"))) == 1
        assert len(list(reader.stream())) == 3

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
# Tests LoopPatcher
# ──────────────────────────────────────────────────────────────────────────────

class TestLoopPatcher:

    def test_create_patch_from_jsonl(self, tmp_path):
        """Test creating a patch from a JSONL file."""
        from looplib.patcher import LoopPatcher, PatchError

        # Create base .loop file
        base_path = tmp_path / "base.loop"
        writer = LoopWriter(base_path, metadata={"name": "base"})
        writer.add_many(SAMPLE_RECORDS[:20])
        writer.save()

        # Create JSONL with new records
        new_records_path = tmp_path / "new_records.jsonl"
        with open(new_records_path, "w") as f:
            for i in range(5):
                record = {
                    "messages": [
                        {"role": "user", "content": f"New Q{i}"},
                        {"role": "assistant", "content": f"New A{i}"},
                    ],
                    "quality": 0.8,
                    "split": "train",
                }
                f.write(json.dumps(record) + "\n")

        # Create patch
        patch_path = tmp_path / "update.looppatch"
        size = LoopPatcher.create(base_path, new_records_path, patch_path)
        assert size > 0
        assert patch_path.exists()

    def test_apply_patch(self, tmp_path):
        """Test applying a patch to a base file."""
        from looplib.patcher import LoopPatcher

        # Create base .loop file
        base_path = tmp_path / "base.loop"
        writer = LoopWriter(base_path, metadata={"name": "base"})
        writer.add_many(SAMPLE_RECORDS[:20])
        writer.save()

        # Create JSONL with new records
        new_records_path = tmp_path / "new_records.jsonl"
        new_records = []
        with open(new_records_path, "w") as f:
            for i in range(5):
                record = {
                    "messages": [
                        {"role": "user", "content": f"New Q{i}"},
                        {"role": "assistant", "content": f"New A{i}"},
                    ],
                    "quality": 0.8,
                    "split": "train",
                }
                new_records.append(record)
                f.write(json.dumps(record) + "\n")

        # Create and apply patch
        patch_path = tmp_path / "update.looppatch"
        LoopPatcher.create(base_path, new_records_path, patch_path)

        merged_path = tmp_path / "merged.loop"
        size = LoopPatcher.apply(base_path, patch_path, merged_path)
        assert size > 0
        assert merged_path.exists()

        # Verify merged file has all records
        reader = LoopReader(merged_path)
        assert reader.count() == 25  # 20 base + 5 new

    def test_patch_incompatible_crc_raises(self, tmp_path):
        """Test that applying a patch to wrong base file raises error."""
        from looplib.patcher import LoopPatcher, PatchError

        # Create two different base files
        base1_path = tmp_path / "base1.loop"
        writer1 = LoopWriter(base1_path, metadata={"name": "base1"})
        writer1.add_many(SAMPLE_RECORDS[:10])
        writer1.save()

        base2_path = tmp_path / "base2.loop"
        writer2 = LoopWriter(base2_path, metadata={"name": "base2"})
        writer2.add_many(SAMPLE_RECORDS[10:20])
        writer2.save()

        # Create patch for base1
        new_records_path = tmp_path / "new_records.jsonl"
        with open(new_records_path, "w") as f:
            record = {
                "messages": [
                    {"role": "user", "content": "Q"},
                    {"role": "assistant", "content": "A"},
                ],
            }
            f.write(json.dumps(record) + "\n")

        patch_path = tmp_path / "update.looppatch"
        LoopPatcher.create(base1_path, new_records_path, patch_path)

        # Try to apply to base2 - should fail
        merged_path = tmp_path / "merged.loop"
        with pytest.raises(PatchError, match="CRC incompatible"):
            LoopPatcher.apply(base2_path, patch_path, merged_path)

    def test_patch_create_from_list(self, tmp_path):
        """Test creating a patch from a list of records."""
        from looplib.patcher import LoopPatcher

        # Create base .loop file
        base_path = tmp_path / "base.loop"
        writer = LoopWriter(base_path, metadata={"name": "base"})
        writer.add_many(SAMPLE_RECORDS[:10])
        writer.save()

        # Create patch from list
        new_records = [
            {
                "messages": [
                    {"role": "user", "content": f"List Q{i}"},
                    {"role": "assistant", "content": f"List A{i}"},
                ],
            }
            for i in range(3)
        ]

        patch_path = tmp_path / "update.looppatch"
        size = LoopPatcher.create(base_path, new_records, patch_path)
        assert size > 0
        assert patch_path.exists()

        # Apply and verify
        merged_path = tmp_path / "merged.loop"
        LoopPatcher.apply(base_path, patch_path, merged_path)
        reader = LoopReader(merged_path)
        assert reader.count() == 13  # 10 base + 3 new

    def test_patch_empty_records_raises(self, tmp_path):
        """Test that creating a patch with no records raises error."""
        from looplib.patcher import LoopPatcher, PatchError

        # Create base .loop file
        base_path = tmp_path / "base.loop"
        writer = LoopWriter(base_path, metadata={"name": "base"})
        writer.add_many(SAMPLE_RECORDS[:10])
        writer.save()

        # Try to create empty patch
        patch_path = tmp_path / "empty.looppatch"
        with pytest.raises(PatchError, match="Aucun record"):
            LoopPatcher.create(base_path, [], patch_path)

    def test_patch_magic_bytes(self, tmp_path):
        """Test that patch file has correct magic bytes."""
        from looplib.patcher import LoopPatcher, MAGIC_PATCH_HEADER, MAGIC_PATCH_FOOTER

        # Create base .loop file
        base_path = tmp_path / "base.loop"
        writer = LoopWriter(base_path, metadata={"name": "base"})
        writer.add_many(SAMPLE_RECORDS[:10])
        writer.save()

        # Create patch
        new_records = [{"messages": [{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}]}]
        patch_path = tmp_path / "update.looppatch"
        LoopPatcher.create(base_path, new_records, patch_path)

        # Verify magic bytes
        with open(patch_path, "rb") as f:
            header_magic = f.read(4)
            f.seek(-4, 2)
            footer_magic = f.read(4)

        assert header_magic == MAGIC_PATCH_HEADER
        assert footer_magic == MAGIC_PATCH_FOOTER


# ──────────────────────────────────────────────────────────────────────────────
# Tests intégrité
# ──────────────────────────────────────────────────────────────────────────────

class TestStreamingLoopWriter:

    def test_streaming_creates_file(self, tmp_path):
        path = tmp_path / "stream.loop"
        w = StreamingLoopWriter(path)
        w.add(SAMPLE_RECORD)
        w.finalize()
        assert path.exists()
        assert path.stat().st_size > 0

    def test_streaming_round_trip(self, tmp_path):
        path = tmp_path / "stream.loop"
        writer = StreamingLoopWriter(path, metadata={"name": "stream_test", "category": "test"})
        for r in SAMPLE_RECORDS[:20]:
            writer.add(r)
        writer.finalize()

        reader = LoopReader(path)
        records = reader.to_list()
        assert len(records) == 20

    def test_streaming_large_dataset(self, tmp_path):
        """Test streaming with many records to ensure no memory issues."""
        path = tmp_path / "large_stream.loop"
        n = 5000
        
        writer = StreamingLoopWriter(path, block_size=100)
        for i in range(n):
            writer.add({
                "messages": [
                    {"role": "user", "content": f"Q{i}"},
                    {"role": "assistant", "content": f"A{i}"},
                ],
                "quality": 0.7 + (i % 30) / 100,
            })
        writer.finalize()

        reader = LoopReader(path)
        assert reader._header["n_records"] == n
        assert reader.count() == n

    def test_streaming_context_manager_cleanup(self, tmp_path):
        """Test that temp files are cleaned up on exception."""
        path = tmp_path / "fail.loop"
        
        try:
            with StreamingLoopWriter(path) as w:
                w.add(SAMPLE_RECORD)
                raise RuntimeError("Forced error")
        except RuntimeError:
            pass  # Expected

        # Temp file should be cleaned up
        temp_files = list(tmp_path.glob("loop_stream_*.tmp"))
        assert len(temp_files) == 0, f"Temp files not cleaned: {temp_files}"

    def test_streaming_same_as_regular_writer(self, tmp_path):
        """Verify streaming and regular writer produce equivalent output."""
        path1 = tmp_path / "regular.loop"
        path2 = tmp_path / "streaming.loop"

        # Regular writer
        w1 = LoopWriter(path1, metadata={"name": "test"})
        for r in SAMPLE_RECORDS[:50]:
            w1.add(r)
        w1.save()

        # Streaming writer
        w2 = StreamingLoopWriter(path2, metadata={"name": "test"})
        for r in SAMPLE_RECORDS[:50]:
            w2.add(r)
        w2.finalize()

        # Both should produce same number of records
        r1 = LoopReader(path1)
        r2 = LoopReader(path2)
        
        assert r1._header["n_records"] == r2._header["n_records"]
        assert len(r1.to_list()) == len(r2.to_list())


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
