# Changelog

All notable changes to the looplib project will be documented in this file.

## [1.0.3] - 2026-04-23

### Fixed
- `SequencePacker.efficiency()`: the `packed_gpu_usage` formula was mathematically incorrect — it always returned ~100% regardless of actual packing quality (formula simplified to `100 - naive_gpu + naive_gpu = 100`). Now correctly computes `avg_tokens_in_packed_seq / max_seq_len * 100`, which properly reflects fill rate (e.g. 46.9% when 60 tokens pack into one 128-token seq vs 99.9% old value).
- `looplib/basic_usage.py`: fix launch comment path (was `python examples/basic_usage.py`, corrected to `python looplib/basic_usage.py` since examples/ is not a top-level directory).

## [1.0.2] - 2026-04-22

### Added
- `LoopReader.count()`, `to_list()`, `to_jsonl()`, `to_huggingface()` now accept all stream filters:
  `max_quality`, `language`, `tags` (previously only `min_quality` and `split` were supported)
- `LoopReader.to_list()` gains `max_records` parameter to limit loaded records
- `to_huggingface()` now uses lazy generator instead of pre-loading all records into RAM

### Changed
- `LoopReader.packed_sequences()` docstring: clarifies it returns Python lists, not torch.Tensors

## [1.0.1] - 2026-04-21

### Added
- Added `--version` / `-v` flag to CLI for version information
- Added `__repr__` methods to `LoopReader` and `LoopWriter` for better debugging
- Improved docstrings with usage examples

### Changed
- Reformatted `__all__` exports for better readability
- Updated `__main__.py` to include all public exports (`StreamingLoopWriter`, `LoopPatcher`, `PatchError`)

## [1.0.0] - 2026-04-18

### Added
- Initial release of the .loop format
- `LoopWriter` for creating .loop files
- `StreamingLoopWriter` for large datasets without memory issues
- `LoopReader` for streaming/random-access reading
- `SequencePacker` for efficient sequence packing
- `LoopValidator` for record validation
- `LoopPatcher` for incremental dataset updates (.looppatch format)
- Full CLI with commands: info, validate, convert, stats, pack, filter, count, merge, inspect, patch-create, patch-apply
- Comprehensive test suite (55 tests)
- SPEC.md with full binary format specification
