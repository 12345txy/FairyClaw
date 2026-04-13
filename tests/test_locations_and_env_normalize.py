# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Tests for config path resolution and G8 env normalization."""

from __future__ import annotations

from pathlib import Path

import pytest

from fairyclaw.config import env_normalize, locations


def test_resolve_config_dir_prefers_cwd_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cfg = tmp_path / "proj" / "config"
    cfg.mkdir(parents=True)
    monkeypatch.chdir(cfg.parent)
    monkeypatch.delenv("FAIRYCLAW_CONFIG_DIR", raising=False)
    assert locations.resolve_config_dir() == cfg.resolve()


def test_resolve_config_dir_state_root_when_no_cwd_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state_root = tmp_path / "h"
    state_root.mkdir()
    monkeypatch.setenv("FAIRYCLAW_HOME", str(state_root))
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.chdir(empty)
    monkeypatch.delenv("FAIRYCLAW_CONFIG_DIR", raising=False)
    expected = (state_root / "config").resolve()
    assert locations.resolve_config_dir(mkdir=False) == expected
    assert locations.resolve_config_dir(mkdir=True).is_dir()


def test_capabilities_dir_from_env_values_relative(tmp_path: Path) -> None:
    anchor = tmp_path
    v = locations.capabilities_dir_from_env_values(anchor, {"FAIRYCLAW_CAPABILITIES_DIR": "./capabilities"})
    assert v == (anchor / "capabilities").resolve()


def test_normalize_fairyclaw_env_file_writes_absolute_paths(tmp_path: Path) -> None:
    anchor = tmp_path / "root"
    anchor.mkdir()
    cfg_dir = anchor / "config"
    cfg_dir.mkdir()
    env_f = cfg_dir / "fairyclaw.env"
    env_f.write_text(
        "FAIRYCLAW_DATA_DIR=./data\n"
        "FAIRYCLAW_CAPABILITIES_DIR=./capabilities\n"
        "FAIRYCLAW_API_TOKEN=x\n",
        encoding="utf-8",
    )
    env_normalize.normalize_fairyclaw_env_file(env_f, anchor)
    text = env_f.read_text(encoding="utf-8")
    assert str((anchor / "data").resolve()) in text
    assert str((anchor / "capabilities").resolve()) in text
    assert "FAIRYCLAW_API_TOKEN=x" in text
