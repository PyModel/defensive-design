# Defensive Design

[![verify](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml/badge.svg)](https://github.com/PyModel/defensive-design/actions/workflows/verify.yml)
[![Agent Skills spec](https://img.shields.io/badge/Agent%20Skills-spec%20compliant-6e5494)](https://agentskills.io/specification)
[![install with skills.sh](https://img.shields.io/badge/skills.sh-npx%20skills%20add-000000)](https://skills.sh)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

An agent skill for defensive coding and production resilience. It guides an agent to
apply the **smallest verified protection** against failures or attacks that can violate
the real contract, without bolting security and resilience machinery onto every
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
- **Classifies before handling.** Caller result, cause, effect certainty, scope, and
  retry policy remain separate. `policy_limit` is not `overloaded`, and
  `unknown_outcome` is not an ordinary timeout.
- **Derives retry safety from semantics.** A repeat-safe lookup, an effectful dequeue,
  and an idempotency-protected payment require different handling regardless of method
  names such as read, write, GET, or POST.
- **Treats recovery as a load source.** Retries, failover, cache rebuilds, autoscaling,
  and the error-handling path itself all create work during the incident they are
  meant to fix.
- **Adds security depth only when needed.** Security-sensitive work loads an on-demand
  overlay for threat modeling, injection sinks, least privilege, secrets and data,
  dependency integrity, and negative verification.
- **Labels every claim with an evidence state.** `verified`, `reasoned_not_run`,
  `blocked`, or `not_applicable`. Confidence is not evidence.

## Package

| Path | Purpose |
|---|---|
| `SKILL.md` | Main skill instructions and trigger metadata |
| `references/failure-taxonomy.md` | Multi-axis results, causes, effect certainty, retry policy, and boundary envelope |
| `references/defensive-checklists.md` | Per-control and failure-path test checklists for Tier 2/3 work |
| `references/secure-coding-overlay.md` | On-demand threat, sink, authority, data, dependency, and security-verification guidance |
| `references/verification-and-chaos.md` | Evidence states, verification matrix, amplification signals, chaos gates, rollout contract |
| `references/resilient_http_example.py` | Illustrative Python outbound-HTTP pattern |
| `scripts/verify_reference.py` | Self-contained regression checks for that pattern |
| `evals/defensive-design.prompts.csv` | Trigger-selection eval prompts |
| `evals/behavior-rubric.md` | Expected behavioral properties for those evals |
| `agents/openai.yaml` | Optional display/invocation metadata |

References load on demand, so the skill stays cheap until the risk surface warrants depth.

## Verify the reference

Requires Python 3.11+ and a current HTTPX 0.x release:

```bash
python -m pip install 'httpx>=0.27,<1'
python scripts/verify_reference.py
```

Forty-three self-contained checks cover path and Unicode validation, telemetry safety,
contract-specific retries, local saturation, cancellation, deterministic breaker
transitions, bounded response reads, hostile headers and encodings, per-phase timeouts,
and hard deadline enforcement. CI runs them on Python 3.11 through 3.14 and installs the
newest available HTTPX as a compatibility canary; applications should keep using their
own reviewed lockfile.

The reference is deliberately illustrative rather than a universal template. Reuse only
the mechanisms justified by the current system's failure surface and existing platform
capabilities.

## License

MIT — see [LICENSE](LICENSE).
