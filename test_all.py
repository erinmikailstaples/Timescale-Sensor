#!/usr/bin/env python3
"""Run every offline test suite in the repository with one command.

    uv run python test_all.py

Nothing here needs hardware, API keys, or a database.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

FOLDERS = ("bridge", "awear", "oura", "examples")


def main() -> int:
    root = Path(__file__).resolve().parent
    failed = 0
    for folder in FOLDERS:
        print(f"\n=== {folder} ===")
        sys.path.insert(0, str(root / folder))
        suite = unittest.defaultTestLoader.discover(str(root / folder), pattern="test_*.py")
        result = unittest.TextTestRunner(verbosity=1).run(suite)
        sys.path.pop(0)
        for name in list(sys.modules):
            if name.startswith("test_"):
                del sys.modules[name]
        failed += len(result.failures) + len(result.errors)
    print("\nALL OK" if failed == 0 else f"\n{failed} problem(s)")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
