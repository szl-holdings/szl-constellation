# SPDX-License-Identifier: Apache-2.0
"""Make the dependency-light publisher modules importable from tools/."""

from __future__ import annotations

import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parents[1]
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
