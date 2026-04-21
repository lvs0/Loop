# Changelog

All notable changes to the looplib project will be documented in this file.

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
