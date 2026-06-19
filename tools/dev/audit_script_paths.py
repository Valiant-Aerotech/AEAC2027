#!/usr/bin/env python3
"""Verify tools/ script path references resolve (post-reorg guard)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"


def main() -> int:
    failures: list[str] = []

    valiant = (TOOLS / "valiant.py").read_text(encoding="utf-8")
    for match in re.finditer(r'_run\("([^"]+)"', valiant):
        path = TOOLS / match.group(1)
        if not path.is_file():
            failures.append(f"valiant.py _run -> {match.group(1)} MISSING")

    dot_source = re.compile(r'^\s*\.\s+\(Join-Path\s+\$PSScriptRoot\s+"([^"]+)"\)', re.MULTILINE)
    ps1_tools_refs = re.compile(r'Join-Path\s+\$ToolsDir\s+"([^"]+)"')
    ps1_amp_refs = re.compile(r'&\s+"\$PSScriptRoot\\([^"]+)"')
    rel_path_refs = re.compile(r'RelativePath\s+"([^"]+)"')

    for ps1 in sorted(TOOLS.rglob("*.ps1")):
        text = ps1.read_text(encoding="utf-8")
        rel = ps1.relative_to(REPO)
        for match in dot_source.finditer(text):
            target = (ps1.parent / match.group(1).replace("/", "\\")).resolve()
            if not target.exists():
                failures.append(f"{rel} dot-source {match.group(1)} -> MISSING")
        for match in ps1_tools_refs.finditer(text):
            target = (TOOLS / match.group(1).replace("/", "\\")).resolve()
            if not target.exists():
                failures.append(f"{rel} ToolsDir {match.group(1)} -> MISSING")
        for match in ps1_amp_refs.finditer(text):
            target = (ps1.parent / match.group(1).replace("/", "\\")).resolve()
            if not target.exists():
                failures.append(f"{rel} & PSScriptRoot\\{match.group(1)} -> MISSING")

    for ps1 in (TOOLS / "setup_wsl.ps1", TOOLS / "launch_sitl.ps1"):
        for match in rel_path_refs.finditer(ps1.read_text(encoding="utf-8")):
            target = TOOLS / match.group(1).replace("/", "\\")
            if not target.is_file():
                failures.append(f"{ps1.name} RelativePath {match.group(1)} -> MISSING")

    stale = re.compile(
        r'ValiantToolsDir.*wsl_distro|Join-Path \$PSScriptRoot "wsl_distro'
    )
    for ps1 in TOOLS.rglob("*.ps1"):
        if ps1.name == "verify_ps1.ps1":
            continue
        text = ps1.read_text(encoding="utf-8")
        if stale.search(text):
            failures.append(f"{ps1.relative_to(REPO)} stale wsl_distro path")

    if failures:
        print("Script path audit FAILED:")
        for item in failures:
            print(f"  {item}")
        return 1

    count = len(list(TOOLS.rglob("*.ps1")))
    print(f"OK: {count} PowerShell scripts + valiant.py routes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
