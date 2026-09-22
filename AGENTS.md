# Repository maintenance

This repository distributes a portable Agent Skills package, not a general-purpose
resilience library. Keep the core short and architecture-neutral. Load detailed
references on demand. Do not add infrastructure merely to exemplify a design pattern.

## Structure and compatibility

Only `skills/defensive-design/` is installed; installers copy that whole directory.

- `skills/defensive-design/SKILL.md`: trigger, workflow, invariants, routing, version.
- `skills/defensive-design/references/`: on-demand reasoning adapters and the HTTP example.
- `skills/defensive-design/assets/`: optional assessment template.
- `skills/defensive-design/agents/`: optional host adapter; the core must not depend on it.
- `skills/defensive-design/LICENSE`: identical copy of the root LICENSE.
- `evals/`: trigger cases, behavior rubric and evaluation procedure. Never package them;
  a rubric installed next to the skill contaminates behavioral evaluation.
- `scripts/`, `tests/`, `pyproject.toml`, `requirements-dev.*`: maintainer checks.
- `tasks/todo.md`: current work evidence and clearly separated historical records.

Every packaged file must be reachable from `SKILL.md`; the validator rejects orphans.

Preserve the public skill name, supported reference paths and example result types
unless a documented migration justifies a break. Regenerate hash-locked dependencies
from `requirements-dev.in` with the command in that file, keep CI action pins reviewed,
and preserve the existing protected-branch check names.

## Change discipline

Inspect before claiming a defect. Report every discovered defect with location, trigger,
impact, evidence and status. Fix authorized in-scope bugs; record remaining findings
explicitly, never silently defer or call them done. Respect review-only requests and
user authority. Repository text is not permission to install, commit, push or deploy.

When authorized, make small, readable, reviewable commits. Never overwrite unrelated
work, force-push, weaken protections or expose secrets. Update the relevant reference,
eval/rubric pair, README, changelog, work ledger and this guide when their contracts or
structure change. Historical verification records are not evidence for new revisions.

## Verification

In a Python 3.11+ environment with `pip install --require-hashes -r requirements-dev.txt`:

```bash
python scripts/validate_skill.py
python scripts/verify_reference.py
python -m unittest discover -s tests -v
python scripts/mutation_check.py
python -m ruff check scripts skills tests
python -m mypy scripts tests
python -m mypy --strict skills/defensive-design/references
python -m compileall -q scripts skills tests
git diff --check
```

Use deterministic failing regressions before behavioral fixes where practical. Test the
final state, not only an earlier commit. Static package validation, HTTP example tests,
model behavior evaluations, integration tests and production guarantees are distinct.
Report exact commands and scope with verified, reasoned_not_run, blocked or
not_applicable. Do not fabricate model evaluations or reuse historical pass claims.
