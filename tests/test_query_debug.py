"""Tests for django_utils.query_debug."""

import logging

import pytest
from django_utils import query_debug

from tests.test_app import models


def _run_queries(n):
    for _ in range(n):
        list(models.Sandwich.objects.all())


@pytest.mark.django_db
def test_counts_queries():
    with query_debug.query_budget(warn_at=100) as budget:
        _run_queries(3)
    assert budget.count == 3


@pytest.mark.django_db
def test_warn_logs_once_over_budget(caplog):
    with caplog.at_level(logging.WARNING, logger='django_utils.query_debug'):
        with query_debug.query_budget(warn_at=2):
            _run_queries(4)
    (record,) = caplog.records
    assert '4' in record.getMessage()
    assert '2' in record.getMessage()


@pytest.mark.django_db
def test_no_warning_within_budget(caplog):
    with caplog.at_level(logging.WARNING, logger='django_utils.query_debug'):
        with query_debug.query_budget(warn_at=5):
            _run_queries(3)
    assert not caplog.records


@pytest.mark.django_db
def test_raise_at_raises_on_offending_query():
    with pytest.raises(query_debug.QueryBudgetExceeded) as excinfo:
        with query_debug.query_budget(raise_at=2):
            _run_queries(3)
    assert excinfo.value.count == 3
    assert excinfo.value.raise_at == 2
    assert 'sandwich' in excinfo.value.last_sql.lower()


@pytest.mark.django_db
def test_decorator_usage_counts_per_call():
    @query_debug.query_budget(raise_at=2)
    def two_queries():
        _run_queries(2)

    # Fresh budget per call: calling twice must not accumulate.
    two_queries()
    two_queries()


@pytest.mark.django_db
def test_nested_budgets_count_independently():
    with query_debug.query_budget(warn_at=100) as outer:
        _run_queries(1)
        with query_debug.query_budget(warn_at=100) as inner:
            _run_queries(2)
    assert inner.count == 2
    assert outer.count == 3  # outer wrapper sees inner's queries too


@pytest.mark.django_db
def test_budget_stops_counting_after_exit():
    with query_debug.query_budget(warn_at=100) as budget:
        _run_queries(1)
    _run_queries(5)
    assert budget.count == 1


def test_requires_some_budget():
    with pytest.raises(ValueError):
        query_debug.query_budget()


@pytest.mark.parametrize(
    'kwargs',
    [
        {'warn_at': 0},
        {'raise_at': 0},
        {'warn_at': -1},
        {'warn_at': 10, 'raise_at': 5},
    ],
)
def test_rejects_nonsense_budgets(kwargs):
    with pytest.raises(ValueError):
        query_debug.query_budget(**kwargs)


def test_not_reentrant():
    budget = query_debug.query_budget(warn_at=1)
    with budget:
        with pytest.raises(RuntimeError):
            with budget:
                pass


@pytest.mark.django_db
def test_using_limits_to_one_alias():
    with query_debug.query_budget(warn_at=100, using='default') as budget:
        _run_queries(2)
    assert budget.count == 2
