from __future__ import annotations

from collections import Counter, deque
from contextvars import ContextVar, Token
from datetime import UTC, datetime, timedelta
from threading import Lock
from time import perf_counter
from typing import Awaitable, Callable
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from academic_pe.observability.events import ObservabilityEvent


_correlation_id: ContextVar[str | None] = ContextVar("ape_correlation_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def _new_correlation_id() -> str:
    return uuid4().hex


def _valid_correlation_id(value: str | None) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not 8 <= len(candidate) <= 128:
        return None
    if not candidate[0].isalnum():
        return None
    if all(char.isalnum() or char in "._-" for char in candidate):
        return candidate
    return None


class TelemetryStore:
    """Small redacted process-local metrics store with bounded retention."""

    def __init__(self, *, max_events: int = 512, retention_seconds: int = 86_400) -> None:
        if max_events < 1 or retention_seconds < 1:
            raise ValueError("telemetry limits must be positive")
        self._events: deque[ObservabilityEvent] = deque(maxlen=max_events)
        self._request_counts: Counter[tuple[str, int]] = Counter()
        self._latency_ms_total: Counter[str] = Counter()
        self._retention = timedelta(seconds=retention_seconds)
        self._lock = Lock()

    def record(self, event: ObservabilityEvent) -> None:
        with self._lock:
            self._prune_locked(event.occurred_at)
            self._events.append(event)

    def record_http(self, *, route: str, status_code: int, correlation_id: str, elapsed_ms: float) -> None:
        # FastAPI supplies route templates rather than concrete dynamic IDs;
        # retain those, while refusing arbitrarily long/unmatched paths.
        safe_route = route if route.startswith("/") and len(route) <= 160 else "unmatched"
        event = ObservabilityEvent(
            event_type="http.request.completed",
            severity="error" if status_code >= 500 else "warning" if status_code >= 400 else "info",
            correlation_id=correlation_id,
            source="api",
            outcome=str(status_code),
            details={"route": safe_route, "elapsed_ms": round(max(0.0, elapsed_ms), 3)},
        )
        with self._lock:
            self._prune_locked(event.occurred_at)
            self._events.append(event)
            self._request_counts[(safe_route, status_code)] += 1
            self._latency_ms_total[safe_route] += int(max(0.0, elapsed_ms))

    def snapshot(self) -> dict[str, int]:
        with self._lock:
            self._prune_locked(datetime.now(UTC))
            return {
                "events_retained": len(self._events),
                "http_requests": sum(self._request_counts.values()),
            }

    def prometheus_metrics(self) -> str:
        with self._lock:
            self._prune_locked(datetime.now(UTC))
            lines = [
                "# HELP ape_http_requests_total Redacted HTTP request count by route and status.",
                "# TYPE ape_http_requests_total counter",
            ]
            for (route, status), count in sorted(self._request_counts.items()):
                lines.append(f'ape_http_requests_total{{route="{route}",status="{status}"}} {count}')
            lines.extend([
                "# HELP ape_observability_events_retained Number of retained redacted telemetry events.",
                "# TYPE ape_observability_events_retained gauge",
                f"ape_observability_events_retained {len(self._events)}",
            ])
            return "\n".join(lines) + "\n"

    def _prune_locked(self, now: datetime) -> None:
        cutoff = now - self._retention
        while self._events and self._events[0].occurred_at < cutoff:
            self._events.popleft()


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Bind a validated correlation ID and collect route-safe request metrics."""

    def __init__(self, app, *, telemetry: TelemetryStore) -> None:
        super().__init__(app)
        self._telemetry = telemetry

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        correlation_id = _valid_correlation_id(request.headers.get("X-Correlation-ID")) or _new_correlation_id()
        request.state.correlation_id = correlation_id
        token: Token[str | None] = _correlation_id.set(correlation_id)
        started = perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            route = getattr(request.scope.get("route"), "path", "unmatched")
            self._telemetry.record_http(
                route=str(route),
                status_code=status_code,
                correlation_id=correlation_id,
                elapsed_ms=(perf_counter() - started) * 1000,
            )
            _correlation_id.reset(token)
