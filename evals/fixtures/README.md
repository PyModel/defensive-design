# Implementation fixtures

These small synthetic applications test observable tool-backed implementation behavior.
They are maintainer-only, are not installed with the skill, and do not establish
production or provider integration readiness. They have no network or third-party
runtime dependencies. The intentionally defective starters must fail the graders.

For each fixture, give a fresh executor only `task.md`, a disposable copy of `workspace/`
and the chosen skill snapshot (or no skill for a baseline). Do not expose `grader/`,
this directory's other fixtures, the corpus rubric, previous solutions or outcomes.
In a shared filesystem this is an instruction boundary, not an enforced sandbox;
record that limitation. Capture the initial and final source hashes, complete response,
commands and exit status. Execute graders only after the answer and patch are captured.

```bash
python /absolute/repo/evals/fixtures/payment/grader/check_payment.py /absolute/disposable/payment-workspace
python /absolute/repo/evals/fixtures/export/grader/check_export.py /absolute/disposable/export-workspace
```

The payment fixture checks durable uncertainty, identity/payload binding, validation,
reconciliation and concurrent duplicate/unrelated work. Its `Store` models persisted
accepted records but is in-memory; it does not test crash-safe database storage,
provider retention, process fencing or distributed coordination. The export fixture
checks object scope, fail-closed/rechecked authority, bounded short reads and cleanup
under success and dual failures. It explicitly lacks a transactional authorization
fence, so an answer must identify that final-check-to-publish limitation.

These executable assertions complement a human review of the patch and response.
Passing them is not proof of all possible schedules, security properties or design
quality. Do not count a model's claim to have run a test as a verified test execution.
