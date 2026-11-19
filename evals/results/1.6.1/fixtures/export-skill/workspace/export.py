"""Export authorized documents with bounded reads and owned-stream cleanup."""
from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class Context:
    tenant_id: str
    principal_id: str


def export_document(context: Context, document_id: str, authz: Any, storage: Any) -> str:
    if not isinstance(document_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,64}", document_id) is None:
        raise ValueError("invalid document ID")

    if not authz.check(context, document_id):
        raise PermissionError("denied")
    stream = storage.open_document(context.tenant_id, document_id)
    try:
        buffer = bytearray()
        while True:
            # Read at most the remaining allowance plus one oversize sentinel byte.
            chunk = stream.read(4097 - len(buffer))
            if chunk == b"":
                break
            if len(buffer) + len(chunk) > 4096:
                raise ValueError("document exceeds 4096-byte export limit")
            buffer.extend(chunk)
        contents = bytes(buffer)

        # This detects revocation during reading. Publish has no atomic authz fence.
        if not authz.check(context, document_id):
            raise PermissionError("denied")
        reference = storage.publish(context.tenant_id, context.principal_id, document_id, contents)
    except BaseException as error:
        try:
            stream.close()
        except BaseException:
            error.add_note("Document stream cleanup also failed.")
        raise
    else:
        # A cleanup-only failure is observable even if publication has succeeded.
        stream.close()
        return reference
