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

Every span automatically emits two metrics derived from its name:

- ``<span>.count`` (counter) with an ``outcome`` attribute (``ok`` / ``error``).
- ``<span>.duration_seconds`` (histogram) with the same ``outcome`` attribute.

Like spans, metrics no-op when no MeterProvider is installed.

ADR 0012 records the full rationale.
"""

from __future__ import annotations

import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any

from opentelemetry import metrics, trace

from eden._version import __version__

# Single tracer + meter for everything eden emits. Users who want to
# instrument their own code under eden's spans should fetch the same tracer
# via ``opentelemetry.trace.get_tracer("eden", <version>)``.
_TRACER = trace.get_tracer("eden", __version__)
_METER = metrics.get_meter("eden", __version__)

# Lazy instrument cache keyed by span name. Counters and histograms are
# created on first use so adding a new span site automatically gets metrics
# without code changes elsewhere. OTel SDK deduplicates instruments by
# (name, instrument-type), so re-creation across module reloads is safe.
_counters: dict[str, metrics.Counter] = {}
_histograms: dict[str, metrics.Histogram] = {}


def _counter(name: str) -> metrics.Counter:
    instrument = _counters.get(name)
    if instrument is None:
        instrument = _METER.create_counter(name)
        _counters[name] = instrument
    return instrument


def _histogram(name: str) -> metrics.Histogram:
    instrument = _histograms.get(name)
    if instrument is None:
        instrument = _METER.create_histogram(name, unit="s")
        _histograms[name] = instrument
    return instrument


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
    """Start an eden-owned span as the current span and emit derived metrics.

    ``attributes`` are set on entry. ``None`` values are dropped; non-OTel
    types are stringified. Exceptions raised inside the ``with`` block are
    recorded on the span (``record_exception``) and the span status is set
    to ``ERROR`` before the exception propagates — callers don't need to
    duplicate this in every site.

    On exit a counter (``<name>.count``) and histogram
    (``<name>.duration_seconds``) are recorded with an ``outcome`` attribute
    of ``"ok"`` (no exception) or ``"error"`` (block raised).
    """
    start = time.monotonic()
    outcome = "ok"
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
            outcome = "error"
            s.record_exception(exc)
            s.set_status(trace.Status(trace.StatusCode.ERROR, str(exc)))
            raise
        finally:
            duration = time.monotonic() - start
            tags = {"outcome": outcome}
            _counter(f"{name}.count").add(1, tags)
            _histogram(f"{name}.duration_seconds").record(duration, tags)


def set_attributes(s: trace.Span, attributes: Mapping[str, Any]) -> None:
    """Set OTel-compatible attributes on an existing span; skip ``None`` values."""
    for k, v in attributes.items():
        coerced = _coerce_attr(v)
        if coerced is None:
            continue
        s.set_attribute(k, coerced)


__all__ = ["set_attributes", "span"]
