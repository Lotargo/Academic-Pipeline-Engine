from decimal import Decimal
from uuid import uuid4

import pytest

from academic_pe.providers import CredentialPolicy
from academic_pe.providers.resources import (
    Availability, BudgetKind, BudgetState, FairUsePolicy, ResourceCoordinator,
    ResourceUnavailable, routing_policy,
)


def test_unknown_budget_never_reports_numeric_remaining():
    state = BudgetState(BudgetKind.UNKNOWN)
    assert state.remaining is None
    with pytest.raises(ValueError): BudgetState(BudgetKind.UNKNOWN, limit=Decimal(10))


def test_known_budget_reservation_exhaustion_and_recovery():
    resources = ResourceCoordinator(); user = uuid4()
    resources.set_budget("openai", BudgetState(BudgetKind.KNOWN, limit=Decimal(10)))
    reservation = resources.reserve("openai", user, Decimal(6))
    with pytest.raises(ResourceUnavailable) as error: resources.reserve("openai", user, Decimal(5))
    assert error.value.code == "platform_budget_exhausted" and error.value.byok_available
    resources.settle(reservation.id, Decimal(10))
    assert resources.budget("openai").availability == Availability.EXHAUSTED
    resources.recover("openai")
    assert resources.budget("openai").availability == Availability.AVAILABLE


def test_unknown_budget_allows_best_effort_until_provider_marks_exhausted():
    resources = ResourceCoordinator(); resources.set_budget("ocr", BudgetState(BudgetKind.UNKNOWN))
    reservation = resources.reserve("ocr", uuid4(), Decimal(999))
    resources.release(reservation.id)
    resources.set_budget("ocr", BudgetState(BudgetKind.UNKNOWN, Availability.EXHAUSTED))
    with pytest.raises(ResourceUnavailable): resources.reserve("ocr", uuid4(), Decimal(1))


def test_fair_use_limits_are_per_user():
    resources = ResourceCoordinator(FairUsePolicy(1, 1)); first, second = uuid4(), uuid4()
    resources.enqueue(first)
    with pytest.raises(ResourceUnavailable): resources.enqueue(first)
    resources.enqueue(second)
    resources.start(first)
    with pytest.raises(ResourceUnavailable): resources.start(first)
    resources.finish(first); resources.start(first)


def test_platform_first_and_explicit_byok_policies():
    assert routing_policy(user_selected_byok=False) == CredentialPolicy.PLATFORM_FIRST
    assert routing_policy(user_selected_byok=True) == CredentialPolicy.USER_ONLY
