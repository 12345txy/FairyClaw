# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Materialize and sync bundled capability groups into the writable capabilities directory."""

from __future__ import annotations

import shutil
import time
from pathlib import Path


def _iter_seed_groups(seed_root: Path) -> list[Path]:
    if not seed_root.is_dir():
        return []
    return sorted(p for p in seed_root.iterdir() if p.is_dir())


def group_tree_matches_seed(seed_group: Path, user_group: Path) -> bool:
    """True iff every file under ``seed_group`` exists under ``user_group`` with identical bytes."""
    if not user_group.is_dir():
        return False
    for src in seed_group.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(seed_group)
        dst = user_group / rel
        if not dst.is_file():
            return False
        if src.read_bytes() != dst.read_bytes():
            return False
    return True


def sync_capabilities(
    *,
    seed_root: Path,
    dest_root: Path,
    dry_run: bool = False,
) -> tuple[list[str], list[str]]:
    """Copy missing groups; skip existing groups that differ from seed (user-modified).

    Returns:
        (added_group_names, skipped_modified_names)
    """
    added: list[str] = []
    skipped: list[str] = []
    if not seed_root.is_dir():
        return added, skipped

    dest_root.mkdir(parents=True, exist_ok=True)

    for seed_group in _iter_seed_groups(seed_root):
        name = seed_group.name
        user_group = dest_root / name
        if not user_group.exists():
            if not dry_run:
                shutil.copytree(seed_group, user_group)
            added.append(name)
            continue
        if group_tree_matches_seed(seed_group, user_group):
            continue
        skipped.append(name)
    return added, skipped


def upgrade_capabilities(
    *,
    seed_root: Path,
    dest_root: Path,
    group: str | None = None,
    backup: bool = True,
    dry_run: bool = False,
) -> list[str]:
    """Overwrite group(s) in ``dest_root`` from ``seed_root``. Returns list of upgraded group names."""
    if not seed_root.is_dir():
        return []

    names = [group] if group else [p.name for p in _iter_seed_groups(seed_root)]
    stamp = time.strftime("%Y%m%d%H%M%S")
    upgraded: list[str] = []

    for name in names:
        sg = seed_root / name
        if not sg.is_dir():
            continue
        ug = dest_root / name
        if dry_run:
            upgraded.append(name)
            continue
        dest_root.mkdir(parents=True, exist_ok=True)
        if ug.exists():
            if backup:
                bak = dest_root / f"{name}.bak.{stamp}"
                shutil.move(str(ug), str(bak))
            else:
                shutil.rmtree(ug)
        shutil.copytree(sg, ug)
        upgraded.append(name)
    return upgraded
