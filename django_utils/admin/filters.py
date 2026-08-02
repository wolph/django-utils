import hashlib
import typing
from abc import ABC
from collections.abc import Iterable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, ClassVar

from django import http
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.admin.filters import (
    AllValuesFieldListFilter,
    BooleanFieldListFilter,
    ChoicesFieldListFilter,
    DateFieldListFilter,
    FieldListFilter,
    ListFilter,
    RelatedFieldListFilter,
    RelatedOnlyFieldListFilter,
    SimpleListFilter,
)
from django.core import exceptions
from django.core.cache import cache
from django.db import models
from django.utils import text

__all__ = (
    'AllValuesFieldListFilter',
    'BooleanFieldListFilter',
    'ChoicesFieldListFilter',
    'DateFieldListFilter',
    'FieldListFilter',
    'ListFilter',
    'RelatedFieldListFilter',
    'RelatedOnlyFieldListFilter',
    'SimpleListFilter',
)

CACHE_TIMEOUT = timedelta(minutes=10)


class DropdownMixin:
    template = 'django_utils/admin/dropdown_filter.html'


class Select2Mixin:
    template = 'django_utils/admin/select2_filter.html'

    if TYPE_CHECKING:
        # Provided by whichever `ListFilter` subclass this is mixed into.
        title: Any

    def select_html_id(self) -> str:
        return text.slugify(self.title)

    # Quick hack to re-use the admin select2 files
    Media = widgets.AutocompleteMixin(
        typing.cast(Any, None), typing.cast(Any, None)
    ).media


if TYPE_CHECKING:
    # `LookupFilterMixin` is only ever mixed into a `SimpleListFilter`
    # subclass (see `JSONFieldFilter` below). Deriving from it here, for
    # static analysis only, gives `self.parameter_name`, `self.used_
    # parameters` and `super().__init__()` / `super().expected_
    # parameters()` their real, precise types instead of `Any` or a
    # hand-rolled restatement that can drift from django-stubs. At
    # runtime `_LookupFilterBase` is plain `object`, so the actual base
    # classes and MRO are decided solely by whatever concrete class
    # mixes `LookupFilterMixin` in.
    _LookupFilterBase = SimpleListFilter
else:
    _LookupFilterBase = object


class LookupFilterMixin(_LookupFilterBase):
    """Adds an operator selector to a list filter.

    The operator is read from ``<parameter_name>__op`` and validated
    against :py:attr:`operators` before use. An operator taken from the
    query string and interpolated into a lookup would otherwise be a
    query-injection surface.
    """

    SUPPORTED_OPERATORS: ClassVar[frozenset[str]] = frozenset(
        {
            'exact',
            'contains',
            'icontains',
            'startswith',
            'gt',
            'gte',
            'lt',
            'lte',
            'range',
        }
    )

    operators: ClassVar[tuple[str, ...]] = ('exact',)

    @property
    def operator_parameter_name(self) -> str:
        return f'{self.parameter_name}__op'

    def __init__(
        self,
        request: http.HttpRequest,
        params: dict[str, list[str]],
        model: type[models.Model],
        model_admin: 'admin.ModelAdmin[Any]',
    ) -> None:
        # `SimpleListFilter.__init__` only pops its own `parameter_name`
        # out of the shared `params` dict; it has no notion of the
        # operator param. Left unpopped here, `<field>__op` falls
        # through to Django's "remaining lookup params" and is
        # re-applied as a raw ORM key-transform lookup (matching
        # nothing) instead of being consumed by `get_operator()`.
        super().__init__(request, params, model, model_admin)
        if self.operator_parameter_name in params:
            value = params.pop(self.operator_parameter_name)
            self.used_parameters[self.operator_parameter_name] = value[-1]

    def expected_parameters(self) -> list[str | None]:
        # Mirrors the `__init__` fix above at the metadata level: this is
        # what `FacetsMixin.get_facet_queryset` consults to exclude this
        # filter's own params when computing facet counts for it.
        return [*super().expected_parameters(), self.operator_parameter_name]

    def get_operator(self) -> str:
        operator = self.used_parameters.get(
            self.operator_parameter_name, self.operators[0]
        )
        if operator not in self.operators:
            raise exceptions.SuspiciousOperation(
                f'Unsupported filter operator: {operator!r}'
            )
        return operator


class FilterBase(admin.SimpleListFilter):
    timeout: timedelta | None = None

    def get_lookups_cache_timeout(self) -> float:
        timeout = self.timeout
        if timeout is None:
            timeout = CACHE_TIMEOUT
        return timeout.total_seconds()

    def get_lookups_cache_scope(self, request: http.HttpRequest) -> str:
        """Cache-key component isolating one user's lookups from another's.

        ``lookups()`` honours the ModelAdmin's per-request queryset, which
        may return different rows per user, so cached values must not be
        shared blindly. Override this to return a constant when every user
        of the admin sees the same rows and you want the cache shared.
        Conversely, if ``ModelAdmin.get_queryset()`` scopes by something
        other than the user -- tenant, site, or request host, for example
        -- include that dimension in the returned string too, or the cache
        key won't vary with it and the leak persists across it.
        """
        user = getattr(request, 'user', None)
        return str(getattr(user, 'pk', None))

    def get_lookups_cache_key(self, request: http.HttpRequest) -> str:
        # Hashed so the key is valid for every cache backend: the raw
        # path + title can contain spaces and exceed memcached's 250
        # byte limit.
        raw = (
            f'{request.get_full_path()}\n{self.title}\n'
            f'{self.get_lookups_cache_scope(request)}'
        )
        digest = hashlib.sha256(raw.encode('utf-8')).hexdigest()
        return f'django_utils.lookups.{digest}'

    def set_lookups_cache(
        self,
        request: http.HttpRequest,
        lookups: list[tuple[Any, str]],
    ) -> None:
        timeout = self.get_lookups_cache_timeout()
        if timeout:
            cache.set(self.get_lookups_cache_key(request), lookups, timeout)

    def get_lookups_cache(
        self, request: http.HttpRequest
    ) -> list[tuple[Any, str]] | None:
        return typing.cast(
            'list[tuple[Any, str]] | None',
            cache.get(self.get_lookups_cache_key(request)),
        )

    def formatter(self, value: Any) -> str:
        """Formatter to convert the value in human readable output"""
        return str(value).title()


class JSONFieldFilter(LookupFilterMixin, FilterBase):
    field_path: str | None = None

    @staticmethod
    def cast(value: str) -> Any:
        return value

    @property
    def attribute_path(self) -> str:
        return typing.cast(str, self.field_path).split('__', 1)[1]

    def lookups(
        self,
        request: http.HttpRequest,
        # Quoted: `admin.ModelAdmin` has no runtime `__class_getitem__`,
        # only django-stubs' stub-only generic. An unquoted subscript
        # would raise TypeError at class-body evaluation time.
        model_admin: 'admin.ModelAdmin[Any]',
    ) -> Iterable[tuple[Any, str]]:
        """The list of value/label pairs for the filter bar with caching"""
        assert self.field_path, '`field_path` is required'

        cached = self.get_lookups_cache(request)
        if cached:
            return cached

        values = (
            model_admin.get_queryset(request)
            .values_list(
                self.field_path,
                flat=True,
            )
            .order_by(self.field_path)
            .distinct()
        )

        lookups = [(value, self.formatter(value)) for value in values]
        self.set_lookups_cache(request, lookups)

        return lookups

    def queryset(
        self,
        request: http.HttpRequest,
        queryset: models.QuerySet[Any],
    ) -> models.QuerySet[Any]:
        value = self.value()
        if not value:
            return queryset

        operator = self.get_operator()
        lookup = typing.cast(str, self.field_path)
        if operator != 'exact':
            lookup = f'{lookup}__{operator}'

        return queryset.filter(**{lookup: self.cast(value)})

    @classmethod
    def create(
        cls,
        field_path: str,
        title: str | None = None,
        parameter_name: str | None = None,
        template: str | None = None,
        formatter: typing.Callable[[typing.Any], str] | None = None,
        cast: typing.Callable[[str], typing.Any] | None = None,
        timeout: timedelta | None = None,
        operators: tuple[str, ...] | None = None,
    ) -> type['JSONFieldFilter']:
        """Build a `JSONFieldFilter` subclass for one JSON sub-path.

        This validation -- including the `contains`/`range` rejection
        below -- only runs for filters built through this factory. A
        direct subclass that sets `operators` as a class attribute
        instead of calling `create()` bypasses it; that is an accepted
        limitation, not something worth metaclass machinery to close.
        """
        assert '__' in field_path, (
            'Paths require both the field and parameter. For example: '
            '`some_json_field__some_parameter`'
        )
        namespace: dict[str, Any] = {
            'field_path': field_path,
            'title': title or ' '.join(field_path.split('_')).title(),
            'parameter_name': parameter_name or field_path,
            'timeout': timeout,
        }
        if operators is not None:
            if not operators:
                raise ValueError(
                    '`operators` must not be empty: an empty tuple '
                    'leaves `get_operator()` with no default and no '
                    'valid operator, failing with `IndexError` on the '
                    'first request instead of at class-creation time.'
                )
            unsupported = (
                set(operators) - LookupFilterMixin.SUPPORTED_OPERATORS
            )
            if unsupported:
                raise ValueError(
                    f'Unsupported operators: {sorted(unsupported)}. '
                    'Supported: '
                    f'{sorted(LookupFilterMixin.SUPPORTED_OPERATORS)}'
                )
            namespace['operators'] = tuple(operators)

        # `contains` and `range` are members of the generic `SUPPORTED_
        # OPERATORS` allowlist -- they're legitimate for ordinary
        # (non-JSON) fields, so `LookupFilterMixin` keeps allowing them --
        # but both silently misbehave once applied to a JSON sub-path
        # (a `KeyTransform`), which is all this factory ever builds.
        # Reject them here, at class-creation time, rather than at
        # request time or (worse) not at all on PostgreSQL.
        json_unsafe_reasons = {
            'contains': (
                '`contains` on a JSON sub-path resolves to '
                "`KeyTransform`'s JSON-containment lookup (PostgreSQL "
                '`@>`), not substring matching, and is unsupported on '
                'SQLite. Use `icontains` for substring matching.'
            ),
            'range': (
                '`range` expects a two-element sequence, but a filter '
                'only ever supplies a single scalar value.'
            ),
        }
        if operators:
            json_unsafe = [
                json_unsafe_reasons[operator]
                for operator in sorted(json_unsafe_reasons)
                if operator in operators
            ]
            if json_unsafe:
                raise ValueError(' '.join(json_unsafe))

        numeric = {'gt', 'gte', 'lt', 'lte', 'range'}
        if operators and numeric.intersection(operators) and cast is None:
            raise ValueError(
                f'Operators {sorted(numeric.intersection(operators))} '
                'compare numerically but no `cast` was given, so values '
                'from the query string would be compared as strings. '
                'Pass cast=int or cast=float.'
            )

        if template is not None:
            namespace['template'] = template
        if formatter is not None:
            namespace['formatter'] = staticmethod(formatter)
        if cast is not None:
            namespace['cast'] = staticmethod(cast)
        return typing.cast(
            'type[JSONFieldFilter]', type('Filter', (cls,), namespace)
        )


class JSONFieldFilterSelect2(Select2Mixin, JSONFieldFilter):
    pass


class SimpleListFilterSelect2(Select2Mixin, SimpleListFilter, ABC):
    pass


class AllValuesFieldListFilterSelect2(Select2Mixin, AllValuesFieldListFilter):
    pass


class ChoicesFieldListFilterSelect2(Select2Mixin, ChoicesFieldListFilter):
    pass


class RelatedFieldListFilterSelect2(Select2Mixin, RelatedFieldListFilter):
    pass


class RelatedOnlyFieldListFilterSelect2(
    Select2Mixin, RelatedOnlyFieldListFilter
):
    pass


class JSONFieldFilterDropdown(DropdownMixin, JSONFieldFilter):
    pass


class SimpleListFilterDropdown(DropdownMixin, SimpleListFilter, ABC):
    pass


class AllValuesFieldListFilterDropdown(
    DropdownMixin, AllValuesFieldListFilter
):
    pass


class ChoicesFieldListFilterDropdown(DropdownMixin, ChoicesFieldListFilter):
    pass


class RelatedFieldListFilterDropdown(DropdownMixin, RelatedFieldListFilter):
    pass


class RelatedOnlyFieldListFilterDropdown(
    DropdownMixin, RelatedOnlyFieldListFilter
):
    pass
