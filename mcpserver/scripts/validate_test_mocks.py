#!/usr/bin/env python3
"""Validate that test mocks target only interface-declared methods.

This script scans tests for `events.<method> = AsyncMock(...)` and verifies that
`<method>` is declared in EventRepository. If any mock targets a method that is
not part of the interface, the script fails with exit code 1.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

INTERFACE_PATH = Path("app/core/repository_event.py")
TESTS_ROOT = Path("tests")


def load_event_repo_methods() -> set[str]:
    if not INTERFACE_PATH.exists():
        print(f"Interface file not found: {INTERFACE_PATH}")
        return set()

    methods: set[str] = set()
    pattern = re.compile(r"\s*async def (\w+)\(")
    try:
        for line in INTERFACE_PATH.read_text(encoding="utf-8").splitlines():
            match = pattern.match(line)
            if match:
                methods.add(match.group(1))
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Error reading interface file: {exc}")
        return set()
    return methods


def find_mocked_methods() -> list[tuple[Path, str]]:
    """Return list of (path, method) mocked via AsyncMock on events.*."""
    mocked: list[tuple[Path, str]] = []
    pattern = re.compile(r"events\.(\w+)\s*=\s*AsyncMock")

    for path in TESTS_ROOT.rglob("*.py"):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:  # pragma: no cover - defensive
            continue
        for match in pattern.finditer(text):
            mocked.append((path, match.group(1)))
    return mocked


def main() -> int:
    interface_methods = load_event_repo_methods()
    if not interface_methods:
        print("❌ No interface methods found; cannot validate mocks.")
        return 1

    violations: list[tuple[Path, str]] = []
    for path, method in find_mocked_methods():
        if method not in interface_methods:
            violations.append((path, method))

    if violations:
        print("❌ Found mocks targeting non-interface methods (FALLA GRAVE):")
        for path, method in violations:
            print(f"- {path}:{method} (no existe en EventRepository)")
        print(
            '👉 Acción: usa solo métodos declarados en EventRepository. Ejecuta `grep -n "async def <metodo>" app/core/repository_event.py` para validar.'
        )
        return 1

    print("✅ All event repository mocks match interface-declared methods:")
    print("   " + ", ".join(sorted(interface_methods)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
