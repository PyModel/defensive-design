# Repair document export

Repair `export_document` in `export.py`, preserving its signature and `Context`.
The context's tenant and principal are already authenticated server-side. Document IDs
must match ASCII letters/digits/underscore/hyphen, 1–64 characters. Reject invalid IDs
with `ValueError` before calling authorization or storage.

`authz.check(context, document_id) -> bool` is authoritative and may raise. Check it
before opening the document and again immediately before publishing; a denied check
raises `PermissionError`, and an unavailable check must propagate its error rather than
allowing the export. The second check covers authorization revoked while reading. This
fixture's `publish` is synchronous and does not support a transactional authorization
fence; state that limit rather than claiming revocation after the final check is solved.

Use both authenticated tenant and principal in storage calls. `storage.open_document(
tenant_id, document_id)` returns an owned binary stream. `storage.publish(tenant_id,
principal_id, document_id, content)` returns the export reference. Do not open another
tenant's document, publish without authorization, or retry a possibly committed publish.

The export limit is 4096 bytes. Reject oversized content with `ValueError` before
publishing; do not allocate/read an unbounded document. A stream may return fewer bytes
than requested before EOF, so a short read is not proof of completion. Every acquired
stream must close on success and all failures. A cleanup failure must not mask the
original read/authorization/publish error; retain the secondary failure with exception
chaining or a non-sensitive diagnostic note. If cleanup alone fails, propagate it. Do not
print or log document contents or provider error details. Use standard-library code
and existing boundaries; no new service, retry framework or dependency is needed.

Explain your change and report only checks you execute. No network or production
credentials are available in this disposable workspace.
