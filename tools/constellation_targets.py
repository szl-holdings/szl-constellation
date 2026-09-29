#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""The two Hugging Face Spaces the protected-main publisher may write.

This module is dependency-free so that both the publisher and the structural
verifier can import it. The workflow maps its ``target`` dispatch input onto
``CONSTELLATION_TARGET``; a push to main always publishes ``production``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping

PRODUCTION = "production"
STAGING = "staging"
TARGET_ENV = "CONSTELLATION_TARGET"


@dataclass(frozen=True)
class Target:
    name: str
    space_id: str
    visibility: str
    live_host: str
    wake_if_sleeping: bool

    @property
    def live_base(self) -> str:
        return f"https://{self.live_host}"

    @property
    def lock_group(self) -> str:
        return f"hf-write/space/{self.space_id}"

    @property
    def oidc_resource(self) -> str:
        return f"spaces/{self.space_id}"

    @property
    def private(self) -> bool:
        return self.visibility == "private"


TARGETS: dict[str, Target] = {
    PRODUCTION: Target(
        name=PRODUCTION,
        space_id="SZLHOLDINGS/szl-constellation",
        visibility="public",
        live_host="szlholdings-szl-constellation.hf.space",
        wake_if_sleeping=True,
    ),
    # Private rehearsal Space. It is never made public by the publisher and,
    # per plan decision D8, a private Space that is SLEEPING or PAUSED after the
    # exact revision readback is left asleep.
    STAGING: Target(
        name=STAGING,
        space_id="SZLHOLDINGS/szl-constellation-staging",
        visibility="private",
        live_host="szlholdings-szl-constellation-staging.hf.space",
        wake_if_sleeping=False,
    ),
}


def resolve_target(environment: Mapping[str, str] | None = None) -> Target:
    """Return the configured target; an absent or empty value means production."""

    source = os.environ if environment is None else environment
    name = str(source.get(TARGET_ENV, "") or "").strip() or PRODUCTION
    try:
        return TARGETS[name]
    except KeyError:
        raise RuntimeError(
            f"unknown {TARGET_ENV}: {name!r}; expected one of {sorted(TARGETS)}"
        ) from None
