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

Backend honesty: the correlated subquery lives inside a FROM-clause
derived table (``FROM (SELECT ...) _agg``/``_count``). MySQL earlier
than 8.0.14 cannot reference the outer query's columns from within a
derived table and fails loudly with an unknown-column error. Verified
on SQLite (this repo's CI); expected to work on PostgreSQL and on
MySQL/MariaDB 8.0.14+, but not CI-verified on either.

The column aggregates (``SubquerySum``, ``SubqueryAvg``, ``SubqueryMin``,
``SubqueryMax``) reserve ``agg_value`` as the inner annotation alias —
a queryset whose model has a real field or annotation named
``agg_value`` raises Django's annotation-conflict error.
"""

import typing

from django.core import exceptions
from django.db import models
from django.db.models import expressions


def _relation_queryset(
    model: type[models.Model], relation: str
) -> 'models.QuerySet[typing.Any]':
    """Build the OuterRef-correlated queryset for a named relation."""
    try:
        field = model._meta.get_field(relation)
    except exceptions.FieldDoesNotExist:
        raise ValueError(
            f'unknown relation {relation!r} on {model.__name__}'
        ) from None
    if isinstance(field, (models.ManyToOneRel, models.ManyToManyRel)):
        # Reverse FK / reverse M2M: filter the related model by its own
        # forward field pointing back at us.
        filter_name = field.field.name
    elif isinstance(field, models.ManyToManyField):
        # Forward M2M: filter the related model by the reverse accessor.
        filter_name = field.related_query_name()
    else:
        # ValueError, not TypeError: the field's *value* (a valid but
        # unsupported relation kind) is wrong, not its Python type.
        raise ValueError(  # noqa: TRY004
            f'{relation!r} on {model.__name__} is not a reverse or '
            f'many-to-many relation; pass a queryset instead'
        )
    related = field.related_model
    assert related is not None
    return related._base_manager.filter(  # pyrefly: ignore[missing-attribute]
        **{filter_name: expressions.OuterRef('pk')}
    )


class _RelationNameMixin:
    """Defer construction when given a relation name instead of a queryset.

    ``SubqueryCount('review')`` cannot know the outer model until the
    expression is resolved against a query; ``resolve_expression`` builds
    the real queryset then and delegates to a fully-constructed clone.
    """

    _deferred: (
        'tuple[str, tuple[typing.Any, ...], dict[str, typing.Any]] | None'
    )

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        """Cooperative passthrough link, ahead of ``Subquery`` in the MRO.

        Every concrete subclass sets ``self._deferred`` itself and defines
        its own ``__init__``, but for the non-string (real queryset) path
        each one ends by calling ``super().__init__(...)``, which the MRO
        of ``class SubqueryCount(_RelationNameMixin, expressions.Subquery)``
        routes through here before it reaches ``Subquery.__init__``. This
        override also gives ``type(self)(...)`` in ``resolve_expression``
        below a permissive signature to type-check against, since a bare
        mixin (no ``__init__`` of its own) would otherwise type-check
        against ``object.__init__`` (0 arguments).
        """
        super().__init__(*args, **kwargs)

    def _defer(
        self,
        relation: str,
        args: tuple[typing.Any, ...],
        kwargs: dict[str, typing.Any],
    ) -> None:
        self._deferred = (relation, args, kwargs)

    def resolve_expression(
        self,
        query: typing.Any = None,
        allow_joins: bool = True,
        reuse: 'set[str] | None' = None,
        summarize: bool = False,
        for_save: bool = False,
    ) -> typing.Any:
        if self._deferred is not None:
            relation, args, kwargs = self._deferred
            resolved = type(self)(
                _relation_queryset(query.model, relation), *args, **kwargs
            )
            return resolved.resolve_expression(
                query, allow_joins, reuse, summarize, for_save
            )
        return super().resolve_expression(  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
            query, allow_joins, reuse, summarize, for_save
        )


class SubqueryCount(_RelationNameMixin, expressions.Subquery):
    """``COUNT(*)`` over ``queryset``, evaluated as its own subquery.

    Unsliced inner querysets get their ordering stripped (pointless in an
    aggregate); sliced ones keep it (a top-N slice needs its ordering).

    ``queryset`` may also be a relation name on the model being annotated
    (``SubqueryCount('review')``), resolved at ``resolve_expression`` time
    against reverse FK, reverse M2M, or forward M2M relations.
    """

    template = '(SELECT COUNT(*) FROM (%(subquery)s) _count)'

    def __init__(
        self,
        queryset: 'models.QuerySet[typing.Any] | str',
        **extra: typing.Any,
    ) -> None:
        self._deferred = None
        if isinstance(queryset, str):
            self._defer(queryset, (), extra)
            return
        # order_by() drops pointless subquery ordering; values('pk')
        # shrinks the select list (JSON/text columns never leave the DB).
        if not queryset.query.is_sliced:
            queryset = queryset.order_by()
        kwargs: dict[str, typing.Any] = dict(extra)
        if 'output_field' not in kwargs:
            kwargs['output_field'] = models.IntegerField()
        super().__init__(queryset.values('pk'), **kwargs)


class _SubqueryColumnAggregate(_RelationNameMixin, expressions.Subquery):
    """``<FUNCTION>(column)`` over ``queryset``, as its own subquery.

    Unsliced inner querysets get their ordering stripped (pointless in an
    aggregate); sliced ones keep it (a top-N slice needs its ordering).

    ``queryset`` may also be a relation name on the model being annotated
    (``SubquerySum('topping', 'price')``), resolved at ``resolve_expression``
    time against reverse FK, reverse M2M, or forward M2M relations.
    """

    function: typing.ClassVar[str]
    default_output_field: typing.ClassVar[
        'models.Field[typing.Any, typing.Any] | None'
    ] = None

    def __init__(
        self,
        queryset: 'models.QuerySet[typing.Any] | str',
        column: str,
        *,
        output_field: 'models.Field[typing.Any, typing.Any] | None' = None,
        **extra: typing.Any,
    ) -> None:
        self._deferred = None
        if isinstance(queryset, str):
            defer_kwargs: dict[str, typing.Any] = dict(extra)
            if output_field is not None:
                defer_kwargs['output_field'] = output_field
            self._defer(queryset, (column,), defer_kwargs)
            return
        if not column.isidentifier():
            raise ValueError(
                f'column must be a plain field/annotation name, got {column!r}'
            )
        self.template = (
            f'(SELECT {self.function}(_agg.agg_value) '
            f'FROM (%(subquery)s) _agg)'
        )
        if not queryset.query.is_sliced:
            queryset = queryset.order_by()
        queryset = queryset.values(agg_value=models.F(column))
        if output_field is None:
            output_field = self.default_output_field
        kwargs: dict[str, typing.Any] = dict(extra)
        if output_field is not None:
            kwargs['output_field'] = output_field
        super().__init__(queryset, **kwargs)


class SubquerySum(_SubqueryColumnAggregate):
    """``SUM(column)``; ``None`` for an empty set."""

    function = 'SUM'


class SubqueryAvg(_SubqueryColumnAggregate):
    """``AVG(column)``; defaults to ``FloatField`` output because SQL AVG
    of integers is fractional."""

    function = 'AVG'

    def __init__(
        self,
        queryset: 'models.QuerySet[typing.Any] | str',
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
