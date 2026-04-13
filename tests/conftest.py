# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Pytest hooks: preload ``fairyclaw_plugins.<group>.config`` for direct tool imports in tests."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_CAP_ROOT = _REPO / "fairyclaw" / "capabilities"


@pytest.fixture(scope="session", autouse=True)
def _preload_fairyclaw_plugin_configs() -> None:
    """Mirror Registry naming so scripts can import ``fairyclaw_plugins.*.config``."""
    if not _CAP_ROOT.is_dir():
        return
    for group_dir in sorted(_CAP_ROOT.iterdir()):
        if not group_dir.is_dir():
            continue
        cfg = group_dir / "config.py"
        if not cfg.is_file():
            continue
        mod_name = f"fairyclaw_plugins.{group_dir.name}.config"
        if mod_name in sys.modules:
            continue
        spec = importlib.util.spec_from_file_location(mod_name, cfg)
        if spec is None or spec.loader is None:
            continue
        mod = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = mod
        spec.loader.exec_module(mod)
