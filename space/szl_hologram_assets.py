"""Local assets for SZL Holographic Space Fabric v2."""
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
A11OY_HOLO_CSS = (_ROOT / "szl-space-hologram.css").read_text(encoding="utf-8")
_script = (_ROOT / "szl-space-hologram.js").read_text(encoding="utf-8")
A11OY_HOLO_HEAD = '<script data-szl-space-holo-v2="inline">' + _script.replace("</script>", "<\/script>") + "</script>"

def merge_hologram_css(value):
    return f"{value or ''}\n{A11OY_HOLO_CSS}"

def merge_hologram_head(value):
    return f"{value or ''}\n{A11OY_HOLO_HEAD}"
