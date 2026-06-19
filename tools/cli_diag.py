"""Shared CLI error formatting for tools/valiant.py and tool scripts."""

from __future__ import annotations

import sys
import traceback
from typing import NoReturn


def hint(msg: str) -> None:
    print(f"  -> {msg}", file=sys.stderr)


def error(msg: str, *hints: str, doc: str = "") -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    for h in hints:
        hint(h)
    if doc:
        hint(f"Docs: {doc}")
    hint("Run: python tools/valiant.py diagnose")
    return 1


def fail(msg: str, *hints: str, doc: str = "") -> NoReturn:
    raise SystemExit(error(msg, *hints, doc=doc))


def unexpected(exc: BaseException) -> int:
    print(f"ERROR: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
    hint("Re-run with more context or: python tools/valiant.py diagnose")
    if isinstance(exc, (FileNotFoundError, ModuleNotFoundError, ImportError)):
        hint("Try: .\\tools\\setup.ps1  or  pip install -e .[gcs,cv,dev]")
    traceback.print_exc()
    return 1
