"""Read-only source-fenced runtime-stage observation for public HF Spaces.

Reads only anonymous public Hugging Face Space metadata. A provider RUNNING
stage is not health, evaluation, GPU execution, or release admission.
The exact Space name must already appear in an independently admitted public
census, and both records must agree on its source SHA.

No credentials, authenticated access, weights, dataset content, hardware
changes, direct Space fetches, or execution authority.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

from atlas_public import ORG, _ALLOWED_NAME, _HEX40, cached_public_atlas

SCHEMA = "szl.public-space-runtime-observation/v1"
STAGE_PATTERN = re.compile(r"[A-Z][A-Z_]{1,31}\Z")
HARDWARE_PATTERN = re.compile(r"[A-Za-z0-9_.-]{1,64}\Z")


class RuntimeObservationError(ValueError):
    """Public admission failure with fixed non-secret reason code."""

    def __init__(self, reason_code: str, http_status: int = 503):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.http_status = http_status


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_hub_space(full_id: str) -> Any:
    # token=False is mandatory, even if a local HF login is configured.
    # One public SpaceInfo response provides SHA, visibility and runtime stage.
    from huggingface_hub import HfApi

    api = HfApi(token=False)
    return api.space_info(full_id, timeout=10, token=False)


def observe_public_space_runtime(
    short_name: str, *,
    census_reader: Callable[[], dict] | None = None,
    info_reader: Callable[[str], Any] | None = None,
    clock: Callable[[], str] | None = None,
) -> dict:
    """Observe one public Space, never a request-controlled URL."""
    if type(short_name) is not str or _ALLOWED_NAME.fullmatch(short_name) is None:
        raise RuntimeObservationError("INVALID_PUBLIC_SPACE_NAME", 400)

    full_id = ORG + "/" + short_name
    census_reader = census_reader or cached_public_atlas
    info_reader = info_reader or _read_hub_space
    clock = clock or now_utc

    try:
        census = census_reader()
    except Exception as exc:
        raise RuntimeObservationError("PUBLIC_CENSUS_UNAVAILABLE") from exc

    if (type(census) is not dict
            or census.get("state") != "OBSERVED_PUBLIC_HUB_METADATA"
            or census.get("scope") != "ANONYMOUS_PUBLIC_HUB_ONLY"
            or census.get("private_assets_excluded") is not True
            or type(census.get("nodes")) is not list):
        raise RuntimeObservationError("PUBLIC_CENSUS_UNVERIFIED")

    nodes = [item for item in census["nodes"]
             if type(item) is dict and item.get("id") == "space:" + full_id]
    if len(nodes) != 1 or nodes[0].get("kind") != "space":
        # Private, nonexistent and malformed entities are indistinguishable.
        raise RuntimeObservationError("SPACE_NOT_IN_PUBLIC_CENSUS", 404)

    expected_sha = nodes[0].get("source_revision")
    if type(expected_sha) is not str or _HEX40.fullmatch(expected_sha) is None:
        raise RuntimeObservationError("PUBLIC_SOURCE_REVISION_UNVERIFIED")

    try:
        info = info_reader(full_id)
    except Exception as exc:
        # No upstream status, request ID, headers, tokens or body cross this.
        raise RuntimeObservationError("ANONYMOUS_HUB_SPACE_INFO_UNAVAILABLE") from exc

    if (getattr(info, "id", None) != full_id
            or getattr(info, "private", None) is not False):
        raise RuntimeObservationError("PUBLIC_VISIBILITY_UNVERIFIED", 404)

    source_sha = getattr(info, "sha", None)
    if type(source_sha) is not str or _HEX40.fullmatch(source_sha) is None:
        raise RuntimeObservationError("PUBLIC_SOURCE_REVISION_UNVERIFIED")
    if source_sha != expected_sha:
        raise RuntimeObservationError("SPACE_SOURCE_CHANGED_SINCE_CENSUS", 409)

    runtime = getattr(info, "runtime", None)
    stage = getattr(runtime, "stage", None)
    if type(stage) is not str or STAGE_PATTERN.fullmatch(stage) is None:
        raise RuntimeObservationError("PROVIDER_STAGE_NOT_OBSERVED")

    hardware = getattr(runtime, "hardware", None)
    if hardware is not None:
        if type(hardware) is not str or HARDWARE_PATTERN.fullmatch(hardware) is None:
            hardware = None

    observed_at = clock()
    if type(observed_at) is not str or not 10 <= len(observed_at) <= 48:
        raise RuntimeObservationError("OBSERVATION_TIME_UNAVAILABLE")

    result = {
        "schema": SCHEMA,
        "state": "OBSERVED_PROVIDER_RUNTIME_METADATA",
        "evidence_class": "ANONYMOUS_PUBLIC_HUB_SPACE_INFO",
        "space_id": full_id,
        "census_source_revision": expected_sha,
        "observed_source_revision": source_sha,
        "source_binding": "PUBLIC_CENSUS_SHA_MATCH",
        "provider_stage": stage,
        "provider_hardware": hardware,
        "observed_at": observed_at,
        "census_observed_at": census.get("observed_at"),
        "runtime_readiness": "NOT_EVALUATED",
        "model_execution": "NOT_EVALUATED",
        "signed_execution_provenance": "NOT_EVALUATED",
        "source_byte_attestation": "NOT_EVALUATED",
        "production_qualified": False,
        "execution_authorized": False,
    }
    canonical = json.dumps(result, sort_keys=True, separators=(",", ":"),
                           allow_nan=False, ensure_ascii=False).encode("utf-8")
    result["observation_sha256"] = hashlib.sha256(canonical).hexdigest()
    return result


def failed_public_observation(reason_code: str) -> dict:
    """Fixed public denial shape; never include a private asset name."""
    safe_reasons = frozenset({
        "INVALID_PUBLIC_SPACE_NAME", "PUBLIC_CENSUS_UNAVAILABLE",
        "PUBLIC_CENSUS_UNVERIFIED", "SPACE_NOT_IN_PUBLIC_CENSUS",
        "PUBLIC_SOURCE_REVISION_UNVERIFIED",
        "ANONYMOUS_HUB_SPACE_INFO_UNAVAILABLE",
        "PUBLIC_VISIBILITY_UNVERIFIED", "SPACE_SOURCE_CHANGED_SINCE_CENSUS",
        "PROVIDER_STAGE_NOT_OBSERVED", "OBSERVATION_TIME_UNAVAILABLE",
        "UNEXPECTED_PUBLIC_OBSERVATION_FAILURE",
    })
    return {
        "schema": SCHEMA,
        "state": "UNAVAILABLE",
        "reason_code": reason_code if reason_code in safe_reasons
                       else "UNEXPECTED_PUBLIC_OBSERVATION_FAILURE",
        "provider_stage": None,
        "runtime_readiness": "NOT_EVALUATED",
        "production_qualified": False,
        "execution_authorized": False,
    }
