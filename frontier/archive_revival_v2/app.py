# SPDX-License-Identifier: Apache-2.0
"""Read-only archive revival evidence surface for SZL Constellation."""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any, Final

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse

from registry import REGISTRY_PATH, RegistryError, public_registry, receipt, resolve_repository

HERE: Final = Path(__file__).resolve().parent
STATIC: Final = HERE / "static"
SOURCE_RE = re.compile(r"^[0-9a-f]{40}$")
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,99}$")
CONTROLLED: Final = (
    HERE / "app.py",
    HERE / "registry.py",
    REGISTRY_PATH,
    STATIC / "index.html",
    STATIC / "app.js",
    STATIC / "styles.css",
)


def source_revision() -> dict[str, str]:
    value = os.getenv("SOURCE_REVISION", "").strip().lower()
    if SOURCE_RE.fullmatch(value):
        return {"state": "MEASURED", "revision": value}
    return {"state": "UNAVAILABLE", "revision": "UNAVAILABLE"}


def controlled_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for path in CONTROLLED:
        key = path.relative_to(HERE).as_posix()
        result[key] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else "UNAVAILABLE"
    return result


app = FastAPI(
    title="SZL Constellation Archive Revival",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)


@app.middleware("http")
async def security_headers(request: Request, call_next):  # noqa: ANN001
    response: Response = await call_next(request)
    response.headers.update(
        {
            "Cache-Control": "no-store" if request.url.path.startswith("/api/") else "public, max-age=300",
            "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
            "Referrer-Policy": "no-referrer",
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
        }
    )
    return response


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok", "service": "szl-constellation-archive-revival-v2"}


@app.get("/readyz")
def readyz(response: Response) -> dict[str, Any]:
    missing = [path.relative_to(HERE).as_posix() for path in CONTROLLED if not path.is_file()]
    registry_state = "VALID"
    try:
        public_registry()
    except RegistryError:
        registry_state = "INVALID"
    status = "READY" if not missing and registry_state == "VALID" else "NOT_READY"
    if status != "READY":
        response.status_code = 503
    return {"status": status, "missing": missing, "registry": registry_state, "source": source_revision()}


@app.get("/api/source")
def source() -> dict[str, Any]:
    value = {
        "schema": "szl.constellation-archive-source/v1",
        "repository": "szl-holdings/szl-constellation",
        "source": source_revision(),
        "controlled_files": controlled_hashes(),
        "classification_authority": "szl-holdings/.github:governance/archive-portfolio-v2.json",
        "provider_readback": "UNAVAILABLE_NOT_PERFORMED",
        "mutation_authority": False,
        "repository_admin_authority": False,
        "hugging_face_write_authority": False,
        "secrets_recorded": False,
    }
    value["receipt_sha256"] = receipt(value)
    return value


@app.get("/api/archive-revival")
def archive_revival(
    disposition: str | None = Query(default=None, pattern=r"^(?:SOURCE_OWNER|CONSOLIDATE|HISTORICAL)$"),
    successor: str | None = Query(default=None, max_length=120, pattern=r"^[a-z0-9][a-z0-9._:/-]+$"),
    q: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    try:
        value = public_registry()
    except RegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:240]) from exc
    rows = value["repositories"]
    if disposition:
        rows = [row for row in rows if row["disposition"] == disposition]
    if successor:
        rows = [row for row in rows if row["successor"] == successor]
    if q:
        needle = q.casefold().strip()
        rows = [
            row
            for row in rows
            if needle in f"{row['name']} {row['successor']} {row['capability']} {' '.join(row['showcase'])}".casefold()
        ]
    rows = sorted(rows, key=lambda row: (row["disposition"], row["name"]))
    result = {
        "schema": value["schema"],
        "contract": value["contract"],
        "truth_boundary": value["truth_boundary"],
        "declared_counts": value["counts"],
        "returned_count": len(rows),
        "repositories": rows,
        "provider_readback": "UNAVAILABLE_NOT_PERFORMED",
        "mutation_authority": False,
    }
    result["receipt_sha256"] = receipt(result)
    return result


@app.get("/api/archive-revival/{name}")
def archive_repository(name: str) -> dict[str, Any]:
    if not NAME_RE.fullmatch(name):
        raise HTTPException(status_code=404, detail="unknown repository")
    try:
        row = resolve_repository(name)
    except RegistryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)[:240]) from exc
    if row is None:
        raise HTTPException(status_code=404, detail="unknown repository")
    value = {
        "schema": "szl.archive-revival-repository/v1",
        "repository": row,
        "provider_readback": "UNAVAILABLE_NOT_PERFORMED",
        "live_archive_state": "UNAVAILABLE_NOT_MEASURED",
        "hub_publication_state": "UNAVAILABLE_NOT_MEASURED",
        "runtime_state": "UNAVAILABLE_NOT_MEASURED",
    }
    value["receipt_sha256"] = receipt(value)
    return value


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC / "index.html", media_type="text/html")


@app.get("/app.js")
def javascript() -> FileResponse:
    return FileResponse(STATIC / "app.js", media_type="text/javascript")


@app.get("/styles.css")
def stylesheet() -> FileResponse:
    return FileResponse(STATIC / "styles.css", media_type="text/css")


@app.exception_handler(HTTPException)
async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"status": "ERROR", "detail": exc.detail})
