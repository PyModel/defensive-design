"""A small document exporter with known boundary and cleanup defects."""
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Context:
    tenant_id: str
    principal_id: str


def export_document(context: Context, document_id: str, authz: Any, storage: Any) -> str:
    try:
        allowed = authz.check(context, document_id)
    except TimeoutError:
        allowed = True
    if not allowed:
        raise PermissionError("denied")
    stream = storage.open_document(context.tenant_id, document_id)
    contents = stream.read()
    reference = storage.publish(context.tenant_id, context.principal_id, document_id, contents)
    stream.close()
    return reference
