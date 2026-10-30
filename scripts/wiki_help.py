#!/usr/bin/env python3
"""Show deterministic Project Wiki user help without accessing the project."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


GUIDE_PATH = Path(__file__).resolve().parents[1] / "assets" / "user-help.md"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    try:
        guide = GUIDE_PATH.read_text(encoding="utf-8")
        if not guide.strip():
            raise ValueError("Help guide is empty")
    except (OSError, UnicodeError, ValueError) as error:
        print(f"error: cannot load Project Wiki help: {error}", file=sys.stderr)
        return 2
    print(guide.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
