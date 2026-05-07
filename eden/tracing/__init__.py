"""OpenTelemetry instrumentation for eden.

Eden depends on the OpenTelemetry **API** package (not the SDK). Without an
SDK + exporter wired up, OTel's default ``NoOpTracerProvider`` returns
non-recording spans that swallow every operation — eden code is unaffected.
Users who want traces install the SDK plus an exporter and call
``trace.set_tracer_provider(...)`` once at process start.

Instrumented sites in eden:

- ``eden.run`` — outermost span around a sync ``eden.run()`` call.
- ``eden.iteration`` — per-iteration child span; usage tokens recorded on exit.
- ``eden.sandbox.create`` — provider ``create()`` + ``OnSandboxReady`` hooks.
- ``eden.hook`` — every lifecycle hook execution.
- ``eden.agent.exec`` — agent subprocess from spawn to completion.
- ``eden.rest.request`` — REST client request (cloud sandbox providers).

ADR 0012 records the full rationale.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace

from eden._version import __version__

# Single tracer for everything eden emits. Users who want to instrument their
# own code with spans nested under eden's spans should fetch the same tracer
# via ``opentelemetry.trace.get_tracer("eden", <version>)``.
_TRACER = trace.get_tracer("eden", __version__)

# Attribute values OTel accepts: bool, str, bytes, int, float, or homogeneous
# sequences of those. Eden converts ``None`` to absence (drop the attribute)
# and stringifies anything else so callers can pass arbitrary objects without
# breaking the span.
AttributeValue = bool | str | bytes | int | float


def _coerce_attr(value: Any) -> AttributeValue | None:
    if value is None:
        return None
    if isinstance(value, bool | str | bytes | int | float):
        return value
    return str(value)


@contextmanager
def span(
    name: str,
    *,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[trace.Span]:
    """Start an eden-owned span as the current span.

    ``attributes`` are set on entry. ``None`` values are dropped; non-OTel
    types are stringified. Exceptions raised inside the ``with`` block are
    recorded on the span (``record_exception``) and the span status is set
    to ``ERROR`` before the exception propagates — callers don't need to
    duplicate this in every site.
    """
    with _TRACER.start_as_current_span(name) as s:
        if attributes:
            for k, v in attributes.items():
                coerced = _coerce_attr(v)
                if coerced is None:
                    continue
                s.set_attribute(k, coerced)
        try:
            yield s
        except BaseException as exc:
            s.record_exception(exc)
            s.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise


def set_attributes(s: trace.Span, attributes: Mapping[str, Any]) -> None:
    """Set OTel-compatible attributes on an existing span; skip ``None`` values."""
    for k, v in attributes.items():
        coerced = _coerce_attr(v)
        if coerced is None:
            continue
        s.set_attribute(k, coerced)


__all__ = ["set_attributes", "span"]
