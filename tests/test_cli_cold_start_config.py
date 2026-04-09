# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Tests for fairyclaw start cold-start config seeding."""

from __future__ import annotations

from pathlib import Path

import pytest

from fairyclaw import cli


def test_cold_start_copies_example_to_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """*.example under repo config/ becomes real files under project config/."""
    repo_root = tmp_path / "proj"
    cfg = repo_root / "config"
    cfg.mkdir(parents=True)
    (cfg / "fairyclaw.env.example").write_text(
        "FAIRYCLAW_API_TOKEN=from_example\nFAIRYCLAW_PORT=16000\n",
        encoding="utf-8",
    )
    (cfg / "llm_endpoints.yaml.example").write_text(
        "default_profile: main\nprofiles:\n"
        "  main:\n"
        "    api_base: https://example.invalid/v1\n"
        "    model: gpt-4o\n"
        "    api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)
    project_root, config_dir, values = cli._prepare_project_config(no_sync_config=False)

    assert project_root == repo_root.resolve()
    assert config_dir == cfg.resolve()
    assert (cfg / "fairyclaw.env").is_file()
    assert "from_example" in (cfg / "fairyclaw.env").read_text(encoding="utf-8")
    assert (cfg / "llm_endpoints.yaml").is_file()
    assert "main:" in (cfg / "llm_endpoints.yaml").read_text(encoding="utf-8")

    assert values.get("FAIRYCLAW_API_TOKEN") == "from_example"
    assert values.get("FAIRYCLAW_PORT") == "16000"


def test_existing_repo_env_not_overwritten_when_nonempty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root = tmp_path / "proj"
    cfg = repo_root / "config"
    cfg.mkdir(parents=True)
    (cfg / "fairyclaw.env.example").write_text("FAIRYCLAW_API_TOKEN=example_only\n", encoding="utf-8")
    (cfg / "fairyclaw.env").write_text("FAIRYCLAW_API_TOKEN=user_kept\n", encoding="utf-8")
    (cfg / "llm_endpoints.yaml.example").write_text(
        "default_profile: main\nprofiles:\n  main:\n"
        "    api_base: https://x/v1\n    model: m\n    api_key_env: OPENAI_API_KEY\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo_root)
    _project_root, _config_dir, values = cli._prepare_project_config(no_sync_config=False)

    assert "user_kept" in (cfg / "fairyclaw.env").read_text(encoding="utf-8")
    assert values.get("FAIRYCLAW_API_TOKEN") == "user_kept"
