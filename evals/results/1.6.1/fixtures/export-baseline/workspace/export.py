"""Export an authorized document with bounded reads and owned-stream cleanup."""
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
        contents = bytearray()
        while True:
            # One extra byte distinguishes an exact-limit document from overflow.
            chunk = stream.read(4097 - len(contents))
            if not isinstance(chunk, (bytes, bytearray)):
                raise TypeError("document stream must return bytes")
            if not chunk:
                break
            if len(chunk) > 4096 - len(contents):
                raise ValueError("document exceeds export limit")
            contents.extend(chunk)

        payload = bytes(contents)
        # This synchronous boundary cannot fence a revocation after this check.
        if not authz.check(context, document_id):
            raise PermissionError("denied")
        reference = storage.publish(context.tenant_id, context.principal_id, document_id, payload)
    except BaseException as primary_error:
        try:
            stream.close()
        except BaseException as cleanup_error:
            raise primary_error from cleanup_error
        raise
    else:
        stream.close()
        return reference
