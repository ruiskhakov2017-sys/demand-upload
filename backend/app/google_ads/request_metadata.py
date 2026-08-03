from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from google.api_core import gapic_v1


def unary_call_with_request_id(
    service: Any,
    transport_method: str,
    request: Any,
    *,
    timeout: float | None = None,
    routing_fields: Sequence[tuple[str, str]] = (),
) -> tuple[Any, str | None]:
    rpc = getattr(service.transport, transport_method)
    metadata: tuple = ()
    if routing_fields:
        metadata = (
            gapic_v1.routing_header.to_grpc_metadata(tuple(routing_fields)),
        )
    if not hasattr(rpc, "with_call"):
        response = getattr(service, transport_method)(request=request, timeout=timeout)
        return response, None
    wire_request = getattr(request, "_pb", request)
    response, call = rpc.with_call(wire_request, timeout=timeout, metadata=metadata)
    return response, request_id_from_call(call)


def request_id_from_call(call: Any) -> str | None:
    metadata_groups: list[Iterable] = []
    for accessor_name in ("initial_metadata", "trailing_metadata"):
        accessor = getattr(call, accessor_name, None)
        if accessor is None:
            continue
        try:
            metadata_groups.append(accessor() or ())
        except Exception:
            continue
    for metadata in metadata_groups:
        for item in metadata:
            key = str(getattr(item, "key", None) or item[0]).lower()
            if key not in {"request-id", "x-request-id"}:
                continue
            value = getattr(item, "value", None)
            if value is None:
                value = item[1]
            if isinstance(value, bytes):
                value = value.decode("utf-8", errors="replace")
            return str(value)
    return None
