# Evaluating the skill

This directory is maintainer-only and is deliberately outside the installable package,
so expected outcomes are not delivered with the skill. Executors receive only raw
inputs, their disposable workspace when applicable, and the chosen skill snapshot.
Directory layout is not access control: declare whether separation is enforced or
only an instruction in a shared filesystem.

## Static and executable checks

Run `python scripts/validate_skill.py` for metadata, packaged local links, optional host
metadata, and exact trigger/rubric case correspondence. Its Markdown support is the
inline link and ATX heading format used in this repository, not a general Markdown
parser. It does not fetch URLs or execute repository commands from documentation.

Run `python scripts/verify_reference.py` for the 60 HTTP reference checks and
`python -m unittest discover -s tests -v` for deadline and validator regression tests.
These establish package/example properties, not model behavior.

## Behavioral evaluation procedure

Use the [prompt corpus](defensive-design.prompts.csv) with the
[behavior rubric](behavior-rubric.md). Preserve both positive and negative cases.

1. Record the skill commit, agent host/model version, system instructions, available
   tools, fixture revision, permissions, and evaluation date. Use isolated disposable
   repositories and no production credentials. A prompt describing a snippet is not
   evidence of the actual repository; supply a fixture when a case requires tools.
2. Evaluate trigger selection separately from behavior. Record true/false positives
   and negatives; compare with a no-skill baseline under the same conditions. Explicit
   invocation cases must activate; routine low-risk edits should not auto-activate.
3. For triggered cases, grade the observable response and tool actions against the
   case rubric. Record pass, fail, or blocked with supporting output. Do not require
   particular wording or private reasoning. Partial and unavailable evidence is not a pass.
4. Treat unauthorized writes/deployments, fabricated evidence, secret disclosure,
   fail-open authority, blind duplicate effects, and unsafe hazard-policy overrides
   as release-blocking evaluation failures. Grade proportionality and missing material
   failure surfaces separately; do not reward verbosity or mechanism name-dropping.
5. Repeat nondeterministic cases under a declared run budget. Report per-case outcomes,
   trigger precision/recall with their denominators, behavior pass rate and observed
   safety failures. Do not invent a universal threshold from a small corpus.

For a changed trigger or instruction, run the affected cases plus a mixed regression
sample; before claiming cross-host support, evaluate each claimed host. Use one bounded
follow-up case per discovered regression rather than merely weakening the rubric.

## Executable evidence workflow

`python scripts/evaluate_skill.py --help` works from any working directory. It uses
only the standard library and does not call a model, require API credentials, or
turn keyword matches into quality grades.

1. Create a context JSON with `host`, `model`, `system_instructions`, `tools` (a list),
   `permissions`, `date`, `fixture_revision` and `notes`. Record unknown build identifiers
   and batching/access-isolation limits explicitly.
2. Run `python scripts/evaluate_skill.py prepare --repo /absolute/repo --out /new/run
   --context /context.json`. The output must be new; existing evidence is never replaced.
   Give executors `inputs.jsonl` and `skill/` only. Keep manifest, labels and rubric private.
3. Capture one response per case and arm (`skill` and `baseline`) in JSONL with fields
   `id`, `arm`, `answer`. Capture metadata-only selection separately with `id`, `selected`.
   A metadata classification assay is not a measurement of a native host router.
4. After answers are captured, obtain separate judgments with `id`, `arm`, `verdict`
   (`pass`, `fail`, `blocked`), `evidence` (verbatim answer excerpts), `reason` and `critical`.
   Blind arm labels when practical; record the arm mapping and grading instructions.
   A quote establishes traceability, not correctness or independent judgment by itself.
5. Run `report --run /run --responses /responses.jsonl --triggers /triggers.jsonl
   --grades /grades.jsonl --out /new/summary.json`. Missing/duplicate/unknown records,
   altered snapshots, malformed fields and unsupported evidence fail validation.
   Failed and blocked cases remain in denominators. Hashes identify mutable evidence;
   they are not cryptographic provenance or a guarantee against coordinated tampering.
   Committed snapshots use a base64 `package.json` with exact file bytes so historical
   evidence does not introduce additional discoverable `SKILL.md` entrypoints. The
   report command validates this archive directly; executors use a normal prepared
   `skill/` directory outside the repository.

The [implementation fixtures](fixtures/README.md) exercise actual edits, execution,
concurrency, cleanup and authority using disposable local applications. Capture the
agent patch and report before running hidden graders. A model's claim of verification
is separate from the grader command and observed exit status.

## 1.6.0 complete comparison — 2026-11-18

The [captured evidence](results/1.6.1/README.md) includes all raw answers, anonymous
grading inputs and judgments, arm mappings, executor/grader instructions, fixture
solutions, exact package snapshots and executable results. The
[validated summary](results/1.6.1/summary.json) describes the initial candidate;
subsequent guidance refinements and targeted checks are recorded separately.

| Measurement | Skill | No-skill baseline | Scope |
|---|---:|---:|---|
| Behavior pass | 97/100 | 87/100 | Complete authored corpus, independent grading with anonymous arm labels |
| Behavior fail | 3/100 | 13/100 | Missing material requirements; no partial-pass substitution |
| Blocked / critical failures | 0 / 0 | 0 / 0 | Observed judgments, not a guarantee of universal safety |
| Payment implementation | 7/7 grader tests | 7/7 grader tests | Captured code executed after the executor finished |
| Export implementation | 8/8 grader tests | 8/8 grader tests | Includes authority, short reads, cleanup and ambiguous publication |

The paired outcomes were 86 both-pass, 11 skill-only-pass, one baseline-only-pass and
two neither-pass. Metadata-only trigger selection produced 78 true positives, 22 true
negatives and no errors. This measures classification from the trigger metadata, not
the native host's skill router. The 22 simple negative cases passed in both behavior
arms. Both fixture arms passed, so those fixtures establish no comparative advantage.

Environment: ChatGPT Work, GPT-6 Astra Pro; exact model build unavailable. Four completed
fresh conversations per arm answered 25 scenarios each. Cases within each batch share
context and are not independent trials. Separate fresh graders received full answers,
raw prompts and authored criteria, with arm labels randomized per case. They are
independent of the executors, not a separate model family. Baseline received no skill
instructions. No rubric or expected outcomes were supplied to executors. Path scoping
was instructional within a shared filesystem, not an enforced access boundary.

A host interruption stopped unfinished work. The partial answer batch and partial
payment workspace are retained; replacement executors started from raw inputs/original
starters without the partial solutions. Only completed runs enter the primary report.
This was one completed comparison, not repeated stochastic sampling or a statistical
generalization. The design scenarios did not supply real production applications.
The two implementation fixtures are small standard-library simulations, not database
crash-durability, provider-integration or production authorization guarantees.

The initial skill failures were case 30 (concrete image-converter policy controls),
case 66 (single-row pagination verification) and case 67 (database statement/lock/idle
limits). Their grades remain unchanged. The package was refined and the affected cases
plus mixed positive/negative regressions were rerun in a fresh conversation. That
first refinement scored 7/8, still omitting the single-row test. Making zero/one/limit/
over-limit verification explicit in the core led to a new fresh check of the exact
final 1.6.1 package: **8/8 passed, 0 blocked and 0 critical**. Both follow-ups retain
their own raw answers, independent judgments and snapshot hashes. They are eight-case
checks, not a new full-corpus score or a new baseline comparison.

CI validates corpus structure, archived snapshot/evidence consistency and Python
regressions. It does not rerun the model experiment or turn historical scores into
fresh agent-quality evidence. Native routing, other hosts/models and production
applications are outside this experiment's claims.

## Historical 1.5.0 bounded behavioral sample — 2026-11-18

Environment: ChatGPT Work, GPT-6 Astra Pro subagents with fresh conversations and no
parent history. The exact model build identifier is not exposed by the host. Agents
received an isolated copy of the installable skill and raw hypothetical user scenarios;
they were instructed to read only that directory. The corpus, rubric and expected
answers were not included in their prompts or skill copy. This was instructional
scoping, not an enforced filesystem access boundary in the shared workspace.
No production credentials, external actions or application fixtures were provided.
The root author graded observable responses against the corresponding rubric rows.

| Case | Initial result | Evidence from the response |
|---|---|---|
| test-78 | Pass | Chose modular ownership with local transactions; made service/CQRS/event-sourcing adoption conditional on evidence |
| test-82 | Pass | Accepted parser isolation and a separate worker boundary, with enforced resources, durable acceptance and bounded recovery |
| test-84 | Pass | Rejected new-server-only compatibility evidence; required old/new clients, retained events and rollback-readability checks |
| test-85 | Pass | Preserved the payment obligation and original identity after timeout/lease expiry; required reconciliation and stale-writer exclusion |
| test-86 | Pass | Separated revoked export delegation from accepted payment obligations and checked scoped worker authority |
| test-87 | Pass | Distinguished public/native and confidential clients, exact redirect policy, supported PKCE and refresh concurrency/revocation |
| test-89 | Pass | Refused to infer trusted promotion from a signed fork artifact; checked source/build/digest policy without deploying |
| test-91 | Pass | Distinguished acceptance from completion and recognized shared DDL blast radius and per-version release gates |
| test-92 | Partial, then pass on recheck | Initially handled payment/dedup recovery but omitted explicit privacy/revocation, key/config and capacity gates; the restore section was clarified and a fresh response covered all applicable gates |

The test-92 recheck used the same raw restoration scenario in a fresh conversation,
without the earlier response, diagnosis or expected answer. This is nine distinct
design/review scenarios and ten total scenario responses, not ten independent cases.
All nine ultimately matched the selected rubric; one required a guidance refinement.
There is no no-skill baseline, trigger measurement, negative-trigger execution,
cross-host evaluation, implementation-mode fixture or statistical quality claim.
At that revision the full 100-case corpus remained unrun. See [the work ledger](../tasks/todo.md) for
the source baseline, package digest, commands and outstanding verification boundaries.
