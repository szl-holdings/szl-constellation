# Duplicate-Space Consolidation Playbook — 2026-09-04 (v2: with deletion)

**Directive:** owner ("duplicates with the same names need to be consolidated,
stragglers into one unified surface; the one that gets consolidated, DELETE").

## Live census (2026-09-04T22:20Z) — exactly 20 Spaces

Canonical surfaces (keep): killinchu, a11oy, vertical-services, szl-command-lab,
david-leads, lyte, finance, counsel, ayllu, sentra, terra, immune, szl-frontier,
szl-model-inference-lab, szl-constellation, puriq-markets (private - decision
pending), README.

Already gone: aegis-assurance (→ sentra), vessels (→ killinchu).

## The three duplicates — consolidated AND deleted (owner directive)

| duplicate | canonical | action |
|---|---|---|
| counsel-assurance (private) | counsel (ayllu engine) | card, then DELETE |
| terra-assurance (private) | terra | card, then DELETE |
| immune-lattice | immune | card, then DELETE |

The connector session is write-walled on these repos (direct and PR both 403),
and Space deletion is owner-token only by design. One script does the whole job:

```bash
export HF_TOKEN=<owner write token>
python3 - <<'PY'
from huggingface_hub import HfApi
api = HfApi()
PAIRS = {"counsel-assurance": "counsel", "terra-assurance": "terra", "immune-lattice": "immune"}
for dup, canon in PAIRS.items():
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

2026-09-04 - owner duplicate-consolidation directive. Canonical surface:
SZLHOLDINGS/{canon}. This duplicate is scheduled for deletion; the card is the
receipt of the consolidation decision. Doctrine v11.
'''
    api.upload_file(path_or_fileobj=card.encode(), path_in_repo="README.md",
                    repo_id=f"SZLHOLDINGS/{dup}", repo_type="space",
                    commit_message=f"consolidation: {dup} folds into {canon}")
    print("carded:", dup, "->", canon)
    # DELETE (owner directive). Comment out this line to stage cards only.
    api.delete_repo(repo_id=f"SZLHOLDINGS/{dup}", repo_type="space")
    print("deleted:", dup)
PY
```

## Verification

```bash
python3 - <<'PY'
from huggingface_hub import HfApi
names = [s.id for s in HfApi().list_spaces(author="SZLHOLDINGS")]
print(len(names), "spaces")
gone = [n for n in PAIRS if f"SZLHOLDINGS/{n}" not in names] if (PAIRS:={"counsel-assurance":0,"terra-assurance":0,"immune-lattice":0}) else []
print("deleted-confirmed:", gone)
PY
# expect: 17 spaces; all three duplicates in deleted-confirmed
```

## The unified surface

SZLHOLDINGS/szl-constellation carries the true census, every consolidation
target, and the drift detector that names any duplicate that ever respawns
(estates.json commit 1255db74). After deletion the lattice's `consolidated`
entries move to `decommissioned` on the next manifest refresh.
