# SPDX-License-Identifier: MIT
# Copyright (c) 2026 FairyClaw contributors, PKU DS Lab
"""Describe uploaded file bytes for LLM-facing user hints (magic bytes first)."""

from __future__ import annotations

import mimetypes
from typing import Final

import filetype  # type: ignore[import-untyped]

_GENERIC_NAMES: Final[frozenset[str]] = frozenset({"upload", "unnamed", ""})


def _label_from_mime(mime: str | None) -> str:
    if not mime:
        return "unknown type"
    m = mime.split(";")[0].strip().lower()
    table: dict[str, str] = {
        "image/png": "PNG image",
        "image/jpeg": "JPEG image",
        "image/jpg": "JPEG image",
        "image/gif": "GIF image",
        "image/webp": "WebP image",
        "image/svg+xml": "SVG vector image",
        "image/bmp": "BMP image",
        "image/tiff": "TIFF image",
        "application/pdf": "PDF document",
        "text/plain": "plain text",
        "text/markdown": "Markdown text",
        "text/html": "HTML document",
        "application/json": "JSON text",
        "application/zip": "ZIP archive",
        "application/x-tar": "TAR archive",
        "application/gzip": "GZIP archive",
        "audio/mpeg": "MP3 audio",
        "audio/wav": "WAV audio",
        "video/mp4": "MP4 video",
    }
    if m in table:
        return table[m]
    if m.startswith("image/"):
        return "image"
    if m.startswith("video/"):
        return "video"
    if m.startswith("audio/"):
        return "audio"
    if m.startswith("text/"):
        return "text"
    return "file"


def describe_user_upload_for_llm(
    content: bytes,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
) -> str:
    """One short English line describing uploaded content."""
    kind = filetype.guess(content) if content else None
    effective_mime: str | None = kind.mime if kind else None
    if effective_mime is None and mime_type:
        effective_mime = mime_type.split(";")[0].strip().lower() or None
    if effective_mime is None and filename:
        guessed, _ = mimetypes.guess_type(filename)
        effective_mime = guessed
    label = _label_from_mime(effective_mime)
    base = f"The user uploaded a file of type {label}."
    fn = (filename or "").strip()
    if fn and fn not in _GENERIC_NAMES:
        return f"{base} Original filename: {fn}."
    return base
