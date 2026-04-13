# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Normalize path-like FAIRYCLAW_* keys in fairyclaw.env (G8) while preserving comments and order."""

from __future__ import annotations

import re
from pathlib import Path

# Keys whose values are filesystem paths (resolved against path_anchor).
PATH_VALUE_KEYS: frozenset[str] = frozenset(
    {
        "FAIRYCLAW_DATA_DIR",
        "FAIRYCLAW_LLM_ENDPOINTS_CONFIG_PATH",
        "FAIRYCLAW_LOG_FILE_PATH",
        "FAIRYCLAW_CAPABILITIES_DIR",
    }
)

_SQLITE_REL = re.compile(
    r"^(?P<prefix>sqlite\+aiosqlite:///)(\./[^?\#]+)(?P<suffix>.*)$",
    re.IGNORECASE,
)


def _strip_quotes(raw: str) -> str:
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in {'"', "'"}:
        return v[1:-1]
    return v


def resolve_path_value(raw: str, anchor: Path) -> str:
    """Turn a possibly relative path into an absolute string (no trailing slash normalization)."""
    v = _strip_quotes(raw)
    if not v:
        return raw
    p = Path(v)
    if p.is_absolute():
        return str(p.resolve())
    return str((anchor / v).resolve())


def normalize_database_url_value(raw: str, anchor: Path) -> str:
    """Absolutize relative sqlite+aiosqlite URL paths like ``...:///./data/db``."""
    v = raw.strip()
    m = _SQLITE_REL.match(v)
    if not m:
        return raw
    rel = m.group(2)
    abs_path = (anchor / rel).resolve()
    return f"{m.group('prefix')}{abs_path.as_posix()}{m.group('suffix')}"


def normalized_path_updates(anchor: Path, current: dict[str, str]) -> dict[str, str]:
    """Compute absolute replacements for G8 keys present in ``current``."""
    out: dict[str, str] = {}
    for key in PATH_VALUE_KEYS:
        if key not in current:
            continue
        out[key] = resolve_path_value(current[key], anchor)
    if "FAIRYCLAW_DATABASE_URL" in current:
        nu = normalize_database_url_value(current["FAIRYCLAW_DATABASE_URL"], anchor)
        if nu != current["FAIRYCLAW_DATABASE_URL"]:
            out["FAIRYCLAW_DATABASE_URL"] = nu
    return out


def merge_env_keys_preserve_lines(path: Path, updates: dict[str, str]) -> None:
    """Update KEY=value lines in place; append missing keys at end; keep comments and blank lines."""
    if not updates:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    lines = text.splitlines(keepends=True)
    if not lines and not text:
        lines = []
    elif not lines and text:
        lines = [text]

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key, _, _val = stripped.partition("=")
            k = key.strip()
            if k in updates:
                seen.add(k)
                nl = line[: line.index("=") + 1] + updates[k]
                if not nl.endswith(("\n", "\r")):
                    nl += "\n"
                new_lines.append(nl)
                continue
        new_lines.append(line)

    missing = [k for k in updates if k not in seen]
    if missing:
        if new_lines and not new_lines[-1].endswith("\n"):
            new_lines[-1] += "\n"
        for k in missing:
            new_lines.append(f"{k}={updates[k]}\n")

    out = "".join(new_lines)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(out, encoding="utf-8")
    tmp.replace(path)


def normalize_fairyclaw_env_file(env_path: Path, anchor: Path) -> None:
    """Apply G8: absolutize path keys in ``env_path`` if it exists."""
    if not env_path.exists():
        return
    from fairyclaw.config.loader import read_env_file

    cur = read_env_file(env_path)
    updates = normalized_path_updates(anchor, cur)
    if not updates:
        return
    merge_env_keys_preserve_lines(env_path, updates)
