"""Query budgets that are safe to leave in production code paths.

``query_budget`` counts every query a block executes and logs a
structured warning (``warn_at``) or raises (``raise_at``) when the block
exceeds its budget: an always-on guard against N+1 regressions, unlike
test-only tools (``assertNumQueries``) or dev-only profilers
(django-silk, django-debug-toolbar).

The load-bearing design decision: counting is implemented with
``connection.execute_wrapper()``, which is public, documented, and
active regardless
of ``DEBUG``, and free of the per-connection query-log accumulation that
``force_debug_cursor``/``connection.queries`` would cause in a
long-lived production process.
"""

import contextlib
import logging
import typing
from collections import Counter
from collections.abc import Callable

from django import db

logger = logging.getLogger(__name__)

_SQL_TRUNCATE = 200
# execute_wrapper's contract: wrapper(execute, sql, params, many, context).
_Execute = Callable[..., typing.Any]


class QueryBudgetExceeded(Exception):  # noqa: N818
    """A block exceeded its ``raise_at`` query budget."""

    def __init__(self, count: int, raise_at: int, last_sql: str) -> None:
        self.count = count
        self.raise_at = raise_at
        self.last_sql = last_sql
        super().__init__(
            f'Query budget exceeded: query {count} executed with a budget '
            f'of {raise_at}. Offending SQL: {last_sql[:_SQL_TRUNCATE]}'
        )


class query_budget(contextlib.ContextDecorator):  # noqa: N801
    """Count queries in a block; warn and/or raise over budget.

    Usable as a context manager or a decorator::

        with query_budget(warn_at=20, raise_at=100):
            ...


        @query_budget(warn_at=20)
        def view(request): ...

    ``warn_at`` logs a single warning on exit when exceeded (with the
    most-repeated statement, the classic N+1 signature).  ``raise_at``
    raises :class:`QueryBudgetExceeded` from the first over-budget query.
    ``using`` limits counting to one connection alias; the default counts
    every configured connection.  Each decorated call gets a fresh
    budget; instances are single-use per ``with`` (not reentrant).
    Instances are not thread-safe; the decorator form is safe because
    each call gets a fresh instance.
    """

    def __init__(
        self,
        warn_at: int | None = None,
        raise_at: int | None = None,
        *,
        using: str | None = None,
    ) -> None:
        if warn_at is None and raise_at is None:
            raise ValueError('Provide warn_at, raise_at, or both')
        for name, value in (('warn_at', warn_at), ('raise_at', raise_at)):
            if value is not None and value < 1:
                raise ValueError(f'{name} must be >= 1, got {value!r}')
        if warn_at is not None and raise_at is not None and warn_at > raise_at:
            raise ValueError(
                f'warn_at ({warn_at}) above raise_at ({raise_at}) can '
                f'never warn'
            )
        self.warn_at = warn_at
        self.raise_at = raise_at
        self.using = using
        self.count = 0
        self._sql_counts: Counter[str] = Counter()
        self._stack: contextlib.ExitStack | None = None

    def _recreate_cm(self) -> 'query_budget':
        # ContextDecorator hook: a fresh budget per decorated call, so
        # counts never accumulate across calls.
        return query_budget(self.warn_at, self.raise_at, using=self.using)

    def _count_execute(
        self,
        execute: _Execute,
        sql: str,
        params: typing.Any,
        many: bool,
        context: dict[str, typing.Any],
    ) -> typing.Any:
        self.count += 1
        self._sql_counts[sql] += 1
        if self.raise_at is not None and self.count > self.raise_at:
            raise QueryBudgetExceeded(self.count, self.raise_at, sql)
        return execute(sql, params, many, context)

    def __enter__(self) -> 'query_budget':
        if self._stack is not None:
            raise RuntimeError(
                'query_budget instances are single-use; create a new one'
            )
        self.count = 0
        self._sql_counts.clear()
        aliases = (
            [self.using] if self.using is not None else list(db.connections)
        )
        self._stack = contextlib.ExitStack()
        for alias in aliases:
            self._stack.enter_context(
                db.connections[alias].execute_wrapper(self._count_execute)
            )
        return self

    def __exit__(self, *exc_info: object) -> None:
        # __exit__ without __enter__ is not a reachable path (the with
        # statement guarantees pairing); cast instead of assert so branch
        # coverage isn't left with an untakeable arm.
        stack = typing.cast(contextlib.ExitStack, self._stack)
        self._stack = None
        stack.close()
        if self.warn_at is not None and self.count > self.warn_at:
            top_sql, top_count = self._sql_counts.most_common(1)[0]
            logger.warning(
                'Query budget exceeded: %d queries executed where %d were '
                'budgeted; most-repeated statement ran %d times: %.*s',
                self.count,
                self.warn_at,
                top_count,
                _SQL_TRUNCATE,
                top_sql,
            )
