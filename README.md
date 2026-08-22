# Defensive Design

[![verify](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml/badge.svg)](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml)
[![Agent Skills spec](https://img.shields.io/badge/Agent%20Skills-spec%20compliant-6e5494)](https://agentskills.io/specification)
[![install with skills.sh](https://img.shields.io/badge/skills.sh-npx%20skills%20add-000000)](https://skills.sh)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

An agent skill for production resilience. It applies failure-oriented engineering
**proportionally** — the smallest verified protection against the failures that can
actually violate the contract — rather than bolting resilience machinery onto every
function.

## Install

```bash
npx skills add PyModel/defensive-design
```

Works with any agent that supports the [Agent Skills](https://agentskills.io) standard —
Claude Code, Codex CLI, Cursor, Copilot, Windsurf, Gemini CLI, and others.

To install manually, copy this directory into a skill location your agent reads, such as
a repository-scoped `.agents/skills/` or your user-level skill directory.

## What it does

- **Tiers the work by consequence, not size.** A five-line cross-tenant authorization
  check is Tier 3; a thousand-line deterministic formatter over trusted internal data
  stays Tier 0.
- **Classifies failures before handling them.** `absence`, `invalid`, `unauthorized`,
  `conflict`, `overloaded`, `transient_dependency`, `permanent_dependency`,
  `unknown_outcome`, `partial_success`, `stale_work`, `cancelled`,
  `invariant_violation` — each with a default behavior and a retry rule.
- **Separates known failure from unknown outcome.** A timed-out read and a timed-out
  payment POST are not the same problem.
- **Treats recovery as a load source.** Retries, failover, cache rebuilds, autoscaling,
  and the error-handling path itself all create work during the incident they are
  meant to fix.
- **Labels every claim with an evidence state.** `verified`, `reasoned_not_run`,
  `blocked`, or `not_applicable`. Confidence is not evidence.

## Package

| Path | Purpose |
|---|---|
| `SKILL.md` | Main skill instructions and trigger metadata |
| `references/failure-taxonomy.md` | Failure classes, outcome certainty, failure envelope, expression across a boundary |
| `references/defensive-checklists.md` | Per-control and failure-path test checklists for Tier 2/3 work |
| `references/verification-and-chaos.md` | Evidence states, verification matrix, amplification signals, chaos gates, rollout contract |
| `references/resilient_http_example.py` | Illustrative Python outbound-HTTP pattern |
| `scripts/verify_reference.py` | Deterministic regression checks for that pattern |
| `evals/defensive-design.prompts.csv` | Trigger-selection eval prompts |
| `evals/behavior-rubric.md` | Expected behavioral properties for those evals |
| `agents/openai.yaml` | Optional display/invocation metadata |

References load on demand, so the skill stays cheap until the risk surface warrants depth.

## Verify the reference

Requires Python 3.11+ and `httpx`:

```bash
python -m pip install httpx
python scripts/verify_reference.py
```

Twenty deterministic checks cover path encoding, breaker transitions and probe
recovery, bounded response reads, malformed `content-length`, deeply nested JSON,
per-phase timeouts, bounded `Retry-After` handling, and hard deadline enforcement.
CI runs them on Python 3.11 through 3.14.

The reference is deliberately illustrative rather than a universal template. Reuse only
the mechanisms justified by the current system's failure surface and existing platform
capabilities.

## License

MIT — see [LICENSE](LICENSE).
