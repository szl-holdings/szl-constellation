# PAYLOAD v2 — finish Constellation (copy into Grok terminal)

Owner: stephenlutar2-hash. Org: szl-holdings. HF: SZLHOLDINGS.
Grok chat has GitHub. Grok chat does NOT have a Hugging Face connector. You must use huggingface-cli.

## Split
- Runtime: https://a-11-oy.com/command
- Tab: https://a-11-oy.com/command/constellation
- Proof: https://a11oy.net (NO runtime)
- Hologram Space: https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation
- GitHub source: https://github.com/szl-holdings/szl-constellation
- YARQA: https://github.com/szl-holdings/yarqa + Space SZLHOLDINGS/yarqa

## Already merged
- a11oy#1883 pages/constellation.html + a11oy_command_center.py mount /command/constellation
- szl-constellation#2 holo/command.html (Second Brain, Anatomy, 49 tiles)

## Missing (do these)
1. huggingface-cli login  (token with write on SZLHOLDINGS)
2. git clone https://github.com/szl-holdings/szl-constellation.git && cd szl-constellation
3. huggingface-cli upload SZLHOLDINGS/szl-constellation holo/command.html holo/command.html --repo-type space
4. If Space uses app.py / holo/index.html, keep them. Serve command.html as a tab. Do not delete immune or immune-lattice Spaces.
5. Rebuild the a11oy container that serves a-11-oy.com so /command/constellation is 200.
6. In static/shared/szl_command_bar.js add VERBS + overflow item:
   { label: 'Constellation', href: '/command/constellation' }
   and a flag to https://huggingface.co/spaces/SZLHOLDINGS/szl-constellation
7. Smoke:
   curl -sI https://a-11-oy.com/command/constellation | head -n 1
   curl -s https://a-11-oy.com/api/a11oy/v1/lambda | head
   curl -s https://a-11-oy.com/api/a11oy/v1/energy/live | head
   Energy must be MEASURED or UNAVAILABLE. Never invent watts.
8. Squash-merge only szl-holdings PRs. Do not touch other GitHub orgs.

## Honesty
Lambda = Conjecture 1. Catalog DECLARED. Probes MEASURED or UNAVAILABLE. No CDN on command pages.
