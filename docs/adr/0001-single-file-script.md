# ADR-0001: Keep `stream.py` a single file

**Status:** Accepted

## Context

The script is distributed as a standalone download from GitHub Releases and run directly on Ubuntu/Linux Mint machines, with no install step beyond `--install`. Operators copy one file to deploy it.

## Decision

All logic stays in `src/stream.py`. No helper modules, packages, or additional source files. Code that would naturally belong in a separate module is inlined instead.

## Consequences

- Portable: one `curl` downloads a working program.
- No packaging, import paths, or install tooling to maintain.
- The file is large; internal structure is enforced by section banners and single-responsibility functions rather than module boundaries.
- This is a hard constraint, not a style preference — refactoring into multiple files is prohibited.
