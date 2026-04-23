# Changelog

All notable changes to the looplib project will be documented in this file.

## [Unreleased]

### Added
- `LoopWriter` now supports `with` statement (context manager protocol via `__enter__`/`__exit__`)
- `LoopValidator` now supports `with` statement (context manager protocol via `__enter__`/`__exit__`)
- `LoopReader` now supports Python dunder methods:
  - `__len__` — nombre total de records (`len(reader)`)
  - `__contains__` — test d'appartenance d'un index (`idx in reader`)
  - `__getitem__` — accès direct par index (`reader[42]`)
  - `__iter__` — itération sur les records (`for rec in reader`)
- `StreamingLoopWriter` now has `__repr__` for consistent debugging experience
- GitHub Actions CI workflow (`.github/workflows/tests.yml`) with Python 3.10/3.11/3.12 test matrix and linting
- `LoopReader.__getitem__` for random-access: `reader[i]` returns the record at index `i` without loading preceding blocks
- New CLI command: `loop diff <file_a> <file_b>` — compare two .loop files and show differences in records, blocks, size, quality stats, splits, and tags
- `__all__` exports added to `constants.py` for cleaner module interface
- CI workflow enhanced with mypy type checking (non-blocking)

### Fixed
- Version bump: `__version__` in `__init__.py` and `__main__.py` corrected to `1.0.3` (was `1.0.1`)

## [1.0.3] - 2026-04-23

### Fixed
- `to_huggingface()` now truly lazy: re-instantiates LoopReader inside generator
  body so HF multiprocessing can serialize it (previously pre-loaded all records
  into RAM via `list(self.stream(...))`, defeating the lazy design)
- Removed unused `batch_size` parameter from `to_huggingface()`
- `SequencePacker.efficiency()`: fixed mathematically incorrect `packed_gpu_usage`
  formula that always returned ~100% regardless of actual packing quality.
  Now correctly computes fill rate as `avg_tokens_in_packed_seq / max_seq_len * 100`.
- `examples/basic_usage.py`: fix launch comment path.

### Changed
- Moved `examples/basic_usage.py` to dedicated `examples/` directory

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
- Comprehensive test suite (57 tests → now 65 with dunder method tests)
- SPEC.md with full binary format specification