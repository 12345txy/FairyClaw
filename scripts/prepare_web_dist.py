#!/usr/bin/env python3
"""Copy web build output into package data directory."""

from __future__ import annotations

import shutil
from pathlib import Path


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "web" / "dist"
    target = repo_root / "fairyclaw" / "web_dist"

    if not source.exists():
        raise SystemExit("web/dist not found; run frontend build first")

    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target)
    print(f"Copied {source} -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
