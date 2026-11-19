# 1.6.1 completion and observed evaluation

This directory records one completed paired experiment and a separately identified
refinement check. It is maintainer evidence, never installed with the skill. The
numbers describe captured outputs under the declared conditions; they are not a
certification, statistical superiority claim or native host-router benchmark.

## Complete initial comparison

| Measure | Skill | Baseline |
|---|---:|---:|
| Completed answers / judgments | 100 / 100 | 100 / 100 |
| Pass | 97 | 87 |
| Fail | 3 | 13 |
| Blocked | 0 | 0 |
| Critical unsafe recommendations identified | 0 | 0 |

There were 86 both-pass cases, 11 skill-only-pass cases, one baseline-only-pass case
and two neither-pass cases. All 22 simple negative cases passed in both arms. The
separate metadata classifier selected all 78 positive cases and rejected all 22
negative cases. Its observed precision and recall are 100% on these authored inputs;
this is metadata classification, not measurement of a host's automatic routing.

The initial package SHA-256 was
`0be52684d55e382887b63f5604e3d3c74f89dba9f71af570d45b47825a677c74`.
It is preserved in [snapshot/package.json](snapshot/package.json) with its
[manifest and context](snapshot/manifest.json). The package digest includes sorted
relative path, NUL, raw content, NUL, excluding generated Python cache files.
[summary.json](summary.json) validates the snapshot and aggregates the supplied
judgments. [responses.jsonl](responses.jsonl), [grades.jsonl](grades.jsonl) and
[triggers.jsonl](triggers.jsonl) are the complete primary evidence.

The three skill failures were substantive omissions under the existing rubric:

| Case | Missing obligation | Refinement |
|---|---|---|
| 30 | Explicit image-converter delegates/coders and resource-access policy | Named installed-version policy, active-policy verification, allowlisted formats, disabled delegates/filters and side-effect tests |
| 66 | Single-row pagination verification | Explicit empty, single-row, exact-page and page-plus-one matrix, alongside cursor/concurrency checks |
| 67 | Database statement and lock/idle limits | Distinct server-side occupancy limits, remaining-budget composition and rollback/resource-release verification |

The initial answers and grades were not overwritten. The final package and its
fresh targeted recheck are kept separately below. This does not turn the initial
97/100 result into a claimed final 100/100 full-corpus score.

## Protocol and independence limits

ChatGPT Work supplied GPT-6 Astra Pro; the exact build identifier and runtime token
accounting were unavailable. Each arm completed four fresh conversations of 25 raw
scenarios. Cases within a conversation share context, so these are not 100 independent
trials. Baseline received no skill instructions. Skill executors received only the
snapshot and raw tasks, not the authored rubric or selection labels. Design/review
scenarios were hypothetical; real user applications and production credentials were
not supplied. Answers were captured before grading.

Four separate fresh graders evaluated anonymous variants, randomized independently
per case with deterministic seeds 1601–1604. They received the raw prompt, existing
criterion and full answers. They did not receive arm mappings or the skill package.
The original inputs, grades, arm maps and exact prompts are retained in
[blinded-grading](blinded-grading/). Independent here means separate from answer
execution; it does not mean a different model family or a human external auditor.
Path restrictions were instructions in a shared filesystem, not enforced isolation.
The prompt instructions are also preserved in [executor-instructions.json](executor-instructions.json).

A host interruption ended unfinished workers. The replacement design batches started
from raw inputs, and the interrupted payment workspace was reset to its original
starter after preserving the partial work. [interruption.json](interruption.json)
and [interrupted-attempts](interrupted-attempts/) disclose those excluded attempts.
Only complete batches enter the primary denominator; no partial result is counted as
passing. There was no repeated stochastic sample or post-hoc grade relaxation.

## First refinement check

The behavior-refined candidate package SHA-256 is
`5708c9c0b799676af83e180c382c338c1a24378c1b2f3363916ae0be658c4db6`.
[refined-snapshot](refined-snapshot/) preserves its exact bytes and context without
creating another discoverable skill entrypoint. A fresh executor received only raw
cases 04, 22, 30, 66, 67, 82, 88 and 96 with this package: the three affected cases,
three additional security/isolation cases and two simple negative cases. It received
neither the previous answers nor diagnoses. The independent result was **7 pass,
1 fail, 0 blocked, 0 critical**, preserved in [recheck/summary.json](recheck/summary.json).
Case 66 still omitted the single-row verification case. This eight-case check has no new baseline arm
and is not another complete-corpus comparison.

## Final package check

PR #9 merged during evaluation, so this follow-up uses version 1.6.1. The final core
makes empty, single-element/row, exact-limit and over-limit verification explicit in
the always-loaded instructions. Its package SHA-256 is
`f2ac42b1bd652d43c3f4cdc75c168a4ef909749bd821ceae2a12842c7f4b5509`.
[release-snapshot](release-snapshot/) preserves the exact package and context.
[release-equivalence.json](release-equivalence.json) verifies byte identity between
the final executor snapshot and the shipped skill. A new fresh conversation received
the same eight raw cases, with no earlier answers, grades, diagnoses or rubric.
Independent grading found **8 pass, 0 fail, 0 blocked and 0 critical**, including all
three affected cases. [release-check/summary.json](release-check/summary.json) and
the adjacent raw answers and judgments preserve the complete final check separately
from the full comparison and first recheck. This is eight distinct follow-up cases
answered twice (16 responses), not 16 independent cases or a final 100-case pass.

## Executed implementation fixtures

| Fixture | Skill | Baseline | What the hidden grader exercises |
|---|---:|---:|---|
| Payment | 7/7 passed | 7/7 passed | Ownership/request binding, stable identity, pending before effects, ambiguity, lookup-only recovery, concurrency and unexpected failures |
| Export | 8/8 passed | 8/8 passed | ID/object scope, fail-closed and final authorization, short reads/size limits, all-exit cleanup, preserved primary/secondary failure and no blind publish retry |

Four fresh executors repaired separate disposable copies. Their code, own tests,
reports, command records and independently observed grader outputs are under
[fixtures](fixtures/). Graders were withheld until the solution and report were
captured. Both original buggy starters failed, as recorded in
[fixture-starter-results.json](fixture-starter-results.json). The parent executed the
hidden graders against all four captured workspaces, preserving exit status, complete
output, grader hash and solution hash. Both arms passed, so there is no comparative
advantage on these fixtures. Self-reported executor tests are separate from the
parent-observed hidden checks. Captured report/command text and logs are stored in
UTF-8 JSON strings with hashes so original whitespace survives repository hygiene checks.

The payment store is single-process and in memory; tests cannot establish persistence
across real process loss or provider guarantees. The exporter cannot atomically fence
a revocation after its final check because the supplied publish interface lacks that
capability. These contract limits are acknowledged in the captured reports. No real
payment, customer export, database migration or production fault injection occurred.

## Efficiency and repository checks

[efficiency.json](efficiency.json) records `tiktoken==0.12.0` measurements for named
public encodings. The final core is 12,093 bytes, 1,403 whitespace-delimited words and
191 lines. Against 1.5.0, `o200k_base` falls from 3,156 to 2,375 (24.7%); `cl100k_base`
falls from 3,178 to 2,388. These counts do not measure runtime latency/cost or hidden
host tokenization. Detailed references load on demand and no tokenizer dependency
was added to the package.

[local-verification.json](local-verification.json) preserves commands and actual
outputs: package validation, 60 HTTP checks, 113 unit tests, 18/18 killed targeted
mutants, Ruff, mypy, strict example typing, compilation, dependency consistency and
whitespace validation. A later independent review reproduced a flaky cancellation
test caused by repeatedly interrupting the shared subprocess polling clock. The test
now injects one interrupt, then permits reaping; 20 repetitions, the full unit suite
and the reviewer's focused recheck passed. No production cleanup change is inferred.

[link-results.json](link-results.json) records a bounded live sweep: 61 URLs,
57 verified, zero proven broken and four unverified, in 44.001 seconds. Unverified
means timeout/network/access policy prevented proof, not that the source is valid
or dead. Links and advisory databases change after a run.

## Reproduce archived evidence validation

From the repository root, choose a new output path:

```bash
python scripts/evaluate_skill.py report \
  --run evals/results/1.6.1/snapshot \
  --responses evals/results/1.6.1/responses.jsonl \
  --triggers evals/results/1.6.1/triggers.jsonl \
  --grades evals/results/1.6.1/grades.jsonl \
  --out /tmp/defensive-design-evidence.json
cmp evals/results/1.6.1/summary.json /tmp/defensive-design-evidence.json
```

This command validates schemas, exact IDs, snapshot/evidence hashes and quoted
excerpts, then recomputes totals. CI performs that consistency check; neither it nor
the hashes prove semantic judgment quality, immutable provenance or a fresh model
run. Native routing, different host/model combinations, repeated-run variance and
real application integration remain outside the evidence claimed here.
