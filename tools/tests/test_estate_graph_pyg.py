# SPDX-License-Identifier: Apache-2.0
"""CPU checks for the estate-graph PyG job spec. No torch, no launch."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import estate_graph_pyg as pyg

ROOT = Path(__file__).resolve().parents[2]
SPEC = ROOT / "datasets" / "szl-estate-graph" / "pyg-jobspec.v0.json"


def test_validator_matches_csv_and_refuses_launch():
    receipt = pyg.validate(ROOT)
    assert receipt["launchAuthorized"] is False
    assert receipt["trainingStarted"] is False
    assert receipt["imagePushed"] is False
    assert receipt["nodeCount"] == 67
    assert receipt["edgeCount"] == 126
    assert receipt["nodeKinds"] == {
        "estate": 49,
        "vertical": 8,
        "hub": 3,
        "substrate": 7,
    }
    assert receipt["edgeKinds"]["runs-on"] == 56
    assert receipt["edgeKinds"]["synapse"] == 49
    assert sum(receipt["edgeKinds"].values()) == 126
    assert "IMAGE_NOT_BUILT" in receipt["reasons"]
    source = Path(pyg.__file__).read_text(encoding="utf-8")
    assert "import torch" not in source
    assert "torch_geometric" not in source


def test_spec_records_open_licenses_and_forbids_ngc():
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    assert spec["dataset"]["hfApiLicense"] == "apache-2.0"
    assert spec["dataset"]["amaruLicenseCheck"] == "PENDING"
    assert spec["container"]["digest"] == "UNKNOWN"
    assert spec["container"]["status"] == "NOT_BUILT"
    packages = {item["name"]: item for item in spec["container"]["packages"]}
    assert packages["torch-geometric"]["githubSpdx"] == "MIT"
    assert packages["torch"]["githubApiSpdx"] == "NOASSERTION"
    assert spec["container"]["forbiddenRegistries"] == ["nvcr.io", "ngc.nvidia.com"]
    assert "nvcr.io" not in spec["container"]["plannedBase"]
    assert spec["caps"]["perRunUsd"] == 100
    assert spec["caps"]["perDayUsd"] == 500
    assert spec["caps"]["perMonthUsd"] == 5000
    assert spec["launcher"] == "saywa"


def test_enterprise_image_and_built_digest_are_refused(tmp_path: Path):
    for relative in (
        pyg.SPEC_RELATIVE,
        pyg.NODES_RELATIVE,
        pyg.EDGES_RELATIVE,
        pyg.GRAPH_RELATIVE,
    ):
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / relative).read_bytes())
    spec_path = tmp_path / pyg.SPEC_RELATIVE
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    spec["container"]["plannedBase"] = "nvcr.io/nvidia/pytorch:24.01-py3"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(pyg.SpecError) as raised:
        pyg.validate(tmp_path)
    assert raised.value.code == "ENTERPRISE_IMAGE_FORBIDDEN"
    spec = json.loads((ROOT / pyg.SPEC_RELATIVE).read_text(encoding="utf-8"))
    spec["container"]["digest"] = "a" * 64
    spec["container"]["status"] = "BUILT"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(pyg.SpecError) as raised:
        pyg.validate(tmp_path)
    assert raised.value.code == "IMAGE_NOT_BUILT"
