# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Tests for fairyclaw start cold-start config seeding."""

from __future__ import annotations

from pathlib import Path

import pytest

from fairyclaw import cli


def test_cold_start_copies_example_to_repo_then_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """*.example under repo config/ becomes real files, then copies into ~/.fairyclaw layout."""
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
    runtime_home = tmp_path / "runtime"
    _runtime_config_dir, values = cli._sync_runtime_config(runtime_home, no_sync_config=False)

    assert (cfg / "fairyclaw.env").is_file()
    assert "from_example" in (cfg / "fairyclaw.env").read_text(encoding="utf-8")
    assert (cfg / "llm_endpoints.yaml").is_file()
    assert "main:" in (cfg / "llm_endpoints.yaml").read_text(encoding="utf-8")

    rt_env = runtime_home / "config" / "fairyclaw.env"
    rt_llm = runtime_home / "config" / "llm_endpoints.yaml"
    assert rt_env.read_text(encoding="utf-8") == (cfg / "fairyclaw.env").read_text(encoding="utf-8")
    assert rt_llm.read_text(encoding="utf-8") == (cfg / "llm_endpoints.yaml").read_text(encoding="utf-8")

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
    runtime_home = tmp_path / "runtime2"
    _runtime_config_dir, values = cli._sync_runtime_config(runtime_home, no_sync_config=False)

    assert "user_kept" in (cfg / "fairyclaw.env").read_text(encoding="utf-8")
    assert values.get("FAIRYCLAW_API_TOKEN") == "user_kept"
