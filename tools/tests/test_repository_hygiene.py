# SPDX-License-Identifier: Apache-2.0
"""Interpreter output is never part of the tracked source.

The last step of the verify job and of the Space publish job deletes every
``__pycache__`` directory and ``*.pyc``/``*.pyo`` file, then requires
``git status --porcelain`` to be empty. A tracked bytecode file makes that
step fail with nothing but "exit code 1" and blocks publication; these tests
name the offending paths instead.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path, PurePosixPath

import pytest

ROOT = Path(__file__).resolve().parents[2]
INTERPRETER_OUTPUT = (
    "tools/__pycache__/verify_constellation.cpython-313.pyc",
    "tools/tests/__pycache__/conftest.cpython-314-pytest-9.2.0.pyc",
    "space/__pycache__/app.cpython-313.pyc",
    "space/app.pyc",
    "space/app.pyo",
    ".pytest_cache/v/cache/nodeids",
)


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    if shutil.which("git") is None or not (ROOT / ".git").exists():
        pytest.skip("needs a git checkout: tracked-file hygiene is read from the git index")
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True)


def _is_interpreter_output(path: str) -> bool:
    parts = PurePosixPath(path).parts
    return (
        "__pycache__" in parts
        or ".pytest_cache" in parts
        or PurePosixPath(path).suffix in {".pyc", ".pyo"}
    )


def test_no_interpreter_output_is_tracked():
    listing = _git("ls-files", "-z")
    assert listing.returncode == 0, listing.stderr.decode("utf-8", "replace")
    tracked = [entry for entry in listing.stdout.decode("utf-8").split("\0") if entry]
    assert "space/app.py" in tracked, "git index does not describe this repository"
    offending = sorted(path for path in tracked if _is_interpreter_output(path))
    assert offending == [], f"tracked interpreter output; remove it with `git rm`: {offending}"


@pytest.mark.parametrize("path", INTERPRETER_OUTPUT)
def test_gitignore_keeps_interpreter_output_untracked(path):
    assert _is_interpreter_output(path)
    ignored = _git("check-ignore", "--no-index", "--quiet", path)
    assert ignored.returncode == 0, f".gitignore does not cover {path}"
