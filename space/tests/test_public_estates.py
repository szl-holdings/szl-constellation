"""Published estate registries stay off personal Hugging Face accounts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PERSONAL_HUB = "huggingface.co/betterwithage"


def test_estates_json_does_not_reference_personal_huggingface_account():
    manifests = sorted(
        path
        for path in ROOT.rglob("estates.json")
        if path.is_file() and ".git" not in path.parts
    )
    assert {path.relative_to(ROOT).as_posix() for path in manifests} >= {
        "estates.json",
        "space/estates.json",
    }
    offenders = [
        path.relative_to(ROOT).as_posix()
        for path in manifests
        if PERSONAL_HUB in path.read_text(encoding="utf-8")
    ]
    assert offenders == [], f"estates.json references {PERSONAL_HUB}: {offenders}"
