"""Aggregates computed in a subquery, immune to JOIN fan-out.

The classic footgun: ``annotate(Count('review'), Count('topping'))``
implements each aggregate as a JOIN, so aggregating two one-to-many
relations together counts the cartesian product — a sandwich with 2
reviews and 3 toppings reports 6 of each.  Each helper here runs its
aggregate in an independent ``(SELECT ... FROM (subquery))`` instead, so
combining any number of them stays correct::

    from django.db.models import OuterRef
    from django_utils.aggregates import SubqueryCount, SubquerySum

    Sandwich.objects.annotate(
        reviews=SubqueryCount(Review.objects.filter(sandwich=OuterRef('pk'))),
        topping_total=SubquerySum(
            Topping.objects.filter(sandwich=OuterRef('pk')), 'price'
        ),
    )

Annotations built this way support ``filter()`` and ``order_by()`` like
any other.  ``SubqueryCount`` of an empty set is 0; the column
aggregates return ``NULL`` (Python ``None``) for an empty set, matching
SQL — wrap in ``django.db.models.functions.Coalesce`` for a default.
"""

import typing

from django.db import models
from django.db.models import expressions


class SubqueryCount(expressions.Subquery):
    """``COUNT(*)`` over ``queryset``, evaluated as its own subquery."""

    template = '(SELECT COUNT(*) FROM (%(subquery)s) _count)'

    def __init__(
        self, queryset: 'models.QuerySet[typing.Any]', **extra: typing.Any
    ) -> None:
        # order_by() drops pointless subquery ordering; values('pk')
        # shrinks the select list (JSON/text columns never leave the DB).
        kwargs: dict[str, typing.Any] = dict(extra)
        if 'output_field' not in kwargs:
            kwargs['output_field'] = models.IntegerField()
        super().__init__(queryset.order_by().values('pk'), **kwargs)


class _SubqueryColumnAggregate(expressions.Subquery):
    """``<FUNCTION>(column)`` over ``queryset``, as its own subquery."""

    function: typing.ClassVar[str]
    default_output_field: typing.ClassVar[
        'models.Field[typing.Any, typing.Any] | None'
    ] = None

    def __init__(
        self,
        queryset: 'models.QuerySet[typing.Any]',
        column: str,
        *,
        output_field: 'models.Field[typing.Any, typing.Any] | None' = None,
        **extra: typing.Any,
    ) -> None:
        if not column.isidentifier():
            raise ValueError(
                f'column must be a plain field/annotation name, got {column!r}'
            )
        self.template = (
            f'(SELECT {self.function}(_agg.{column}) FROM (%(subquery)s) _agg)'
        )
        if output_field is None:
            output_field = self.default_output_field
        kwargs: dict[str, typing.Any] = dict(extra)
        if output_field is not None:
            kwargs['output_field'] = output_field
        super().__init__(queryset.order_by().values(column), **kwargs)


class SubquerySum(_SubqueryColumnAggregate):
    """``SUM(column)``; ``None`` for an empty set."""

    function = 'SUM'


class SubqueryAvg(_SubqueryColumnAggregate):
    """``AVG(column)``; defaults to ``FloatField`` output because SQL AVG
    of integers is fractional."""

    function = 'AVG'

    def __init__(
        self,
        queryset: 'models.QuerySet[typing.Any]',
        column: str,
        *,
        output_field: 'models.Field[typing.Any, typing.Any] | None' = None,
        **extra: typing.Any,
    ) -> None:
        if output_field is None:
            output_field = models.FloatField()
        super().__init__(queryset, column, output_field=output_field, **extra)


class SubqueryMin(_SubqueryColumnAggregate):
    """``MIN(column)``; ``None`` for an empty set."""

    function = 'MIN'


class SubqueryMax(_SubqueryColumnAggregate):
    """``MAX(column)``; ``None`` for an empty set."""

    function = 'MAX'
