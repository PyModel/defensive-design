# Changelog

## 1.2.0 - 2026-09-04

### Fixed

- The illustrative HTTP client could return success when synchronous parsing or response
  cleanup crossed the operation deadline before the event loop ran its cancellation
  callback. Use the event-loop deadline and check completion time before returning.
  The deadline remains cooperative, not hard real-time preemption.
- Replace blanket rejection of process-local synchronization with state-ownership scope.
- Apply timeout, queue, distributed-state and recovery checks only to actual surfaces.
- Permit explicit low-risk audits and recognize consequential pure computation.

### Added

- Architecture/capability adaptation, optional assessment template and primary-source map.
- Explicit review/design/implementation/incident modes and action-authority boundaries.
- Local, offline, UI, stream, data, infrastructure, device and agent evaluation cases.
- Offline package validation and negative tests; preserve the existing trigger corpus.
- Read-only, pinned-action CI with a reviewed dependency baseline, separate HTTPX
  compatibility checks, bounded runtime and source/environment evidence artifacts.
- Maintenance guidance and distinct package/example/model-evaluation evidence rules.

### Compatibility and limitations

The skill name, existing reference paths and public example result types are retained.
Install the complete package. No application dependency or data migration is required.
Python dependencies are for maintainers and the optional example only. Package checks
and deterministic regressions do not prove autonomous behavior on every codebase.
See README for rollout and rollback, and tasks/todo.md for the current evidence record.
