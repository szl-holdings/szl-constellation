"""Closed static presentation assets, separate from operational API routes."""
from __future__ import annotations

import os
from pathlib import Path
import stat

ROOT = Path(__file__).resolve().parent / "presentation"
MAX_ASSET_BYTES = 256 * 1024
ASSETS = {
    "/assets/szl/szl-tokens.css": ("szl-tokens.css", "text/css; charset=utf-8"),
    "/assets/szl/native.css": ("native.css", "text/css; charset=utf-8"),
    "/assets/szl/native.js": ("native.js", "text/javascript; charset=utf-8"),
    "/assets/szl/szl-icon-32.svg": ("szl-icon-32.svg", "image/svg+xml"),
    "/assets/szl/PROJECTION.json": ("PROJECTION.json", "application/json"),
}


def read_asset(route: str) -> tuple[bytes, str]:
    """Select a literal file and read the same bounded regular descriptor."""
    name, content_type = ASSETS[route]
    descriptor = os.open(ROOT / name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ASSET_BYTES:
            raise OSError("Presentation asset outside regular-file bounds")
        with os.fdopen(descriptor, "rb", closefd=False) as source:
            data = source.read(MAX_ASSET_BYTES + 1)
        if len(data) != info.st_size or len(data) > MAX_ASSET_BYTES:
            raise OSError("Presentation asset changed or exceeds bounds")
        return data, content_type
    finally:
        os.close(descriptor)
