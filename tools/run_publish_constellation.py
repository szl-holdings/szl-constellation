#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the publisher while retaining an explicit failure receipt."""

from __future__ import annotations

import json
import os
from pathlib import Path

from publish_constellation import publish

ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "artifacts" / "constellation-deployment-receipt.json"


def main() -> int:
    try:
        publish()
    except Exception as error:
        RECEIPT.parent.mkdir(parents=True, exist_ok=True)
        failure = {
            "schema": "szl.constellation-deployment/v1",
            "state": "FAILED_CLOSED",
            "source": {
                "repository": os.environ.get("GITHUB_REPOSITORY"),
                "revision": os.environ.get("GITHUB_SHA"),
            },
            "workflow": {
                "runId": os.environ.get("GITHUB_RUN_ID"),
                "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT", "1"),
            },
            "error": {
                "type": type(error).__name__,
                "detail": str(error)[:2000],
            },
            "authority": {
                "hubMutationClaimed": False,
                "liveVerificationClaimed": False,
            },
        }
        RECEIPT.write_text(
            json.dumps(failure, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(failure, sort_keys=True), flush=True)
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
