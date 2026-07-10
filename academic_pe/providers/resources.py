from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from threading import RLock
from typing import Protocol
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from academic_pe.persistence.models import UsageEvent
from .models import CredentialPolicy


class BudgetKind(str, Enum):
    KNOWN = "known"
    UNKNOWN = "unknown"


class Availability(str, Enum):
    AVAILABLE = "available"
    DEGRADED = "degraded"
    EXHAUSTED = "exhausted"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class BudgetState:
    kind: BudgetKind
    availability: Availability = Availability.AVAILABLE
    limit: Decimal | None = None
    used: Decimal = Decimal(0)

    def __post_init__(self) -> None:
        if self.kind == BudgetKind.UNKNOWN and self.limit is not None:
            raise ValueError("unknown budget cannot expose a numeric limit")
        if self.kind == BudgetKind.KNOWN and (self.limit is None or self.limit < 0):
            raise ValueError("known budget requires a non-negative limit")

    @property
    def remaining(self) -> Decimal | None:
        return None if self.limit is None else max(Decimal(0), self.limit - self.used)


@dataclass(frozen=True)
class FairUsePolicy:
    max_active_per_user: int = 1
    max_queued_per_user: int = 3


@dataclass(frozen=True)
class Reservation:
    id: UUID
    provider_id: str
    user_id: UUID
    quantity: Decimal
    created_at: datetime


class ResourceUnavailable(RuntimeError):
    def __init__(self, code: str, message: str, *, byok_available: bool = True):
        super().__init__(message)
        self.code, self.byok_available = code, byok_available


class UsageRecorder(Protocol):
    def record(self, workspace_id: UUID, user_id: UUID, provider_id: str,
               metric: str, quantity: Decimal, metadata: dict[str, object] | None = None) -> None: ...


class SqlAlchemyUsageRecorder:
    def __init__(self, session: Session): self.session = session

    def record(self, workspace_id: UUID, user_id: UUID, provider_id: str,
               metric: str, quantity: Decimal, metadata: dict[str, object] | None = None) -> None:
        self.session.add(UsageEvent(workspace_id=workspace_id, actor_user_id=user_id,
            provider=provider_id, metric=metric, quantity=quantity, metadata_json=metadata or {}))
        self.session.commit()


class ResourceCoordinator:
    """Atomic reference policy; deployments may share it through a persistent adapter later."""

    def __init__(self, policy: FairUsePolicy = FairUsePolicy()):
        if policy.max_active_per_user < 1 or policy.max_queued_per_user < 0:
            raise ValueError("fair-use limits must be non-negative")
        self.policy = policy
        self._budgets: dict[str, BudgetState] = {}
        self._active: dict[UUID, int] = {}
        self._queued: dict[UUID, int] = {}
        self._reservations: dict[UUID, Reservation] = {}
        self._lock = RLock()

    def set_budget(self, provider_id: str, state: BudgetState) -> None:
        with self._lock: self._budgets[provider_id] = state

    def budget(self, provider_id: str) -> BudgetState:
        return self._budgets.get(provider_id, BudgetState(BudgetKind.UNKNOWN))

    def enqueue(self, user_id: UUID) -> None:
        with self._lock:
            if self._queued.get(user_id, 0) >= self.policy.max_queued_per_user:
                raise ResourceUnavailable("fair_use_queue_limit", "Per-user queue limit reached", byok_available=False)
            self._queued[user_id] = self._queued.get(user_id, 0) + 1

    def start(self, user_id: UUID) -> None:
        with self._lock:
            if self._active.get(user_id, 0) >= self.policy.max_active_per_user:
                raise ResourceUnavailable("fair_use_concurrency_limit", "Per-user concurrency limit reached", byok_available=False)
            self._queued[user_id] = max(0, self._queued.get(user_id, 0) - 1)
            self._active[user_id] = self._active.get(user_id, 0) + 1

    def finish(self, user_id: UUID) -> None:
        with self._lock: self._active[user_id] = max(0, self._active.get(user_id, 0) - 1)

    def reserve(self, provider_id: str, user_id: UUID, quantity: Decimal) -> Reservation:
        if quantity <= 0: raise ValueError("reservation quantity must be positive")
        with self._lock:
            state = self.budget(provider_id)
            if state.availability in {Availability.EXHAUSTED, Availability.UNAVAILABLE}:
                raise ResourceUnavailable("platform_resource_unavailable", "Platform resource unavailable; use your own key")
            reserved = sum((r.quantity for r in self._reservations.values() if r.provider_id == provider_id), Decimal(0))
            if state.remaining is not None and reserved + quantity > state.remaining:
                raise ResourceUnavailable("platform_budget_exhausted", "Platform budget exhausted; use your own key")
            item = Reservation(uuid4(), provider_id, user_id, quantity, datetime.now(timezone.utc))
            self._reservations[item.id] = item
            return item

    def settle(self, reservation_id: UUID, actual: Decimal) -> None:
        if actual < 0: raise ValueError("actual usage must be non-negative")
        with self._lock:
            item = self._reservations.pop(reservation_id)
            state = self.budget(item.provider_id)
            used = state.used + actual
            availability = state.availability
            if state.limit is not None and used >= state.limit: availability = Availability.EXHAUSTED
            self._budgets[item.provider_id] = BudgetState(state.kind, availability, state.limit, used)

    def release(self, reservation_id: UUID) -> None:
        with self._lock: self._reservations.pop(reservation_id, None)

    def recover(self, provider_id: str) -> None:
        with self._lock:
            state = self.budget(provider_id)
            self._budgets[provider_id] = BudgetState(state.kind, Availability.AVAILABLE, state.limit, state.used)


def routing_policy(*, user_selected_byok: bool) -> CredentialPolicy:
    return CredentialPolicy.USER_ONLY if user_selected_byok else CredentialPolicy.PLATFORM_FIRST
