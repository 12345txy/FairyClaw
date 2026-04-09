"""Path helpers for source and installed layouts."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def package_dir() -> Path:
    """Return installed package directory for ``fairyclaw``."""
    spec = importlib.util.find_spec("fairyclaw")
    if spec is None or spec.origin is None:
        raise RuntimeError("Cannot resolve fairyclaw package path")
    return Path(spec.origin).resolve().parent


def resolve_web_dist_dir() -> Path:
    """Resolve web dist path for both wheel and source tree runs."""
    override = os.getenv("FAIRYCLAW_WEB_DIST_DIR", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    pkg_dir = package_dir()
    packaged_dist = pkg_dir / "web_dist"
    source_dist = pkg_dir.parent / "web" / "dist"

    for candidate in (packaged_dist, source_dist):
        if (candidate / "index.html").exists():
            return candidate

    return packaged_dist
