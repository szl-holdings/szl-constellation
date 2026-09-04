# Duplicate-Space Consolidation Playbook — 2026-09-04

**Directive:** owner ("duplicates with the same names need to be consolidated,
stragglers into one unified surface").

## Live census (2026-09-04T22:20Z) — exactly 20 Spaces

Canonical surfaces (keep): killinchu, a11oy, vertical-services, szl-command-lab,
david-leads, lyte, finance, counsel, ayllu, sentra, terra, immune, szl-frontier,
szl-model-inference-lab, szl-constellation, puriq-markets (private - decision
pending), README.

Decommissioned already: aegis-assurance (→ sentra), vessels (→ killinchu; removed
from the live census).

## The three duplicates and their cards

The connector session is write-walled on these repos (direct and PR both 403) —
the cards below apply via the owner token. One loop:

```bash
export HF_TOKEN=<owner write token>
for pair in counsel-assurance:counsel terra-assurance:terra immune-lattice:immune; do
  dup="${pair%%:*}"; canon="${pair##*:}"
  python3 - "$dup" "$canon" <<'PY'
import sys
from huggingface_hub import HfApi
dup, canon = sys.argv[1], sys.argv[2]
card = f'''---
title: {dup} -> {canon}
sdk: docker
app_port: 7860
pinned: false
license: apache-2.0
short_description: "CONSOLIDATED - folds into the canonical {canon} surface"
tags: [szl-holdings, governed-ai, consolidated]
---

# {dup} -> {canon} (CONSOLIDATED)

2026-09-04 - owner duplicate-consolidation directive. This Space was a duplicate.
The canonical surface is SZLHOLDINGS/{canon}. The duplicate is reported, not
erased; this card is the standing pointer until the retirement gates close.

Doctrine v11.
'''
HfApi().upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md",
                    repo_id=f"SZLHOLDINGS/{dup}", repo_type="space",
                    commit_message=f"consolidation: {dup} folds into {canon}")
print("carded:", dup, "->", canon)
PY
done
```

## Verification

```bash
for s in counsel-assurance terra-assurance immune-lattice; do
  curl -s "https://huggingface.co/spaces/SZLHOLDINGS/$s/raw/main/README.md" | head -3
done
# expect: the CONSOLIDATED card front-matter on each
```

## The unified surface

The "one space" is the constellation itself: SZLHOLDINGS/szl-constellation now
carries the true 20-Space census, every consolidation target, and the drift
detector that will catch any duplicate that ever comes back (estates.json commit
1255db74).
