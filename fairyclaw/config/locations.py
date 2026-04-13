# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Resolve config, data, and capability paths for repo checkout vs pip / state root layouts."""

from __future__ import annotations

import os
from pathlib import Path

from fairyclaw.paths import package_dir

_ENV_STATE_ROOT = "FAIRYCLAW_HOME"
_ENV_CONFIG_DIR = "FAIRYCLAW_CONFIG_DIR"


def resolve_state_root() -> Path:
    """User state root (default ``~/.fairyclaw``). Overridden by ``FAIRYCLAW_HOME``."""
    raw = os.environ.get(_ENV_STATE_ROOT, "").strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return (Path.home() / ".fairyclaw").resolve()


def resolve_config_dir(*, mkdir: bool = False) -> Path:
    """Config directory: ``FAIRYCLAW_CONFIG_DIR``, else ``cwd/config`` if present, else state root ``config/``."""
    override = os.environ.get(_ENV_CONFIG_DIR, "").strip()
    if override:
        p = Path(override).expanduser().resolve()
        if mkdir:
            p.mkdir(parents=True, exist_ok=True)
        return p

    cwd_cfg = (Path.cwd() / "config").resolve()
    if cwd_cfg.is_dir():
        return cwd_cfg

    p = resolve_state_root() / "config"
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p


def path_anchor() -> Path:
    """Directory that relative paths in ``fairyclaw.env`` are resolved against (parent of ``config/``)."""
    return resolve_config_dir().parent.resolve()


def resolve_fairyclaw_env_path(*, mkdir: bool = False) -> Path:
    p = resolve_config_dir(mkdir=mkdir) / "fairyclaw.env"
    return p


def resolve_capabilities_seed_dir() -> Path:
    """Read-only shipped capability tree inside the installed package (seed source)."""
    return package_dir() / "capabilities"


def resolve_capabilities_dir(*, mkdir: bool = False) -> Path:
    """Writable capability groups root (default ``<path_anchor>/capabilities``)."""
    raw = os.environ.get("FAIRYCLAW_CAPABILITIES_DIR", "").strip()
    if raw:
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = path_anchor() / p
        p = p.resolve()
        if mkdir:
            p.mkdir(parents=True, exist_ok=True)
        return p

    p = path_anchor() / "capabilities"
    if mkdir:
        p.mkdir(parents=True, exist_ok=True)
    return p.resolve()


def default_llm_endpoints_config_path() -> str:
    return str((resolve_config_dir() / "llm_endpoints.yaml").resolve())


def default_capabilities_dir() -> str:
    return str(resolve_capabilities_dir())


def default_data_dir() -> str:
    return str(path_anchor() / "data")


def settings_env_file_tuple() -> tuple[Path, ...]:
    """Absolute env files for Pydantic Settings (primary + optional cwd ``.env``)."""
    primary = resolve_fairyclaw_env_path()
    return (primary, Path.cwd() / ".env")


def capabilities_dir_from_env_values(anchor: Path, values: dict[str, str]) -> Path:
    """Resolve writable capabilities root from parsed ``fairyclaw.env`` (relative to ``anchor``)."""
    raw = (values.get("FAIRYCLAW_CAPABILITIES_DIR") or "").strip()
    if raw:
        if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in {'"', "'"}:
            raw = raw[1:-1]
        p = Path(raw)
        if not p.is_absolute():
            return (anchor / p).resolve()
        return p.resolve()
    return (anchor / "capabilities").resolve()
