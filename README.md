# Defensive Design Skill

A production-resilience skill for ChatGPT/Codex that applies failure-oriented engineering proportionally rather than adding resilience machinery everywhere.

## Package

- `SKILL.md` — main skill instructions and trigger metadata.
- `agents/openai.yaml` — optional display/invocation metadata.
- `references/defensive-checklists.md` — per-control and failure-path test checklists for Tier 2/3 work.
- `references/failure-taxonomy.md` — failure classes, the known-vs-unknown-outcome distinction, the failure envelope, and expressing classes across a boundary.
- `references/verification-and-chaos.md` — evidence states, the per-surface verification matrix, runtime amplification signals, chaos gates, and the rollout/rollback contract.
- `references/resilient_http_example.py` — corrected Python outbound-HTTP reference pattern.
- `scripts/verify_reference.py` — deterministic regression checks for the Python reference.
- `evals/defensive-design.prompts.csv` — trigger-selection eval prompts.
- `evals/behavior-rubric.md` — expected behavioral properties for those evals.

## Local installation

Place the `defensive-design` directory in an appropriate local skill location, for example a repository-scoped `.agents/skills/` directory or the user-level skill directory supported by your Codex setup.

## Reference verification

With Python 3.11+ and `httpx` installed:

```bash
python scripts/verify_reference.py
```

The reference is deliberately illustrative rather than a universal template. Reuse only the mechanisms justified by the current system's failure surface and existing platform capabilities.
