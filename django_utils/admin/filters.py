import hashlib
import typing
from abc import ABC
from collections.abc import Iterable
from datetime import timedelta
from typing import TYPE_CHECKING, Any

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


class JSONFieldFilter(FilterBase):
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
        if value:
            field_path = typing.cast(str, self.field_path)
            return queryset.filter(**{field_path: self.cast(value)})
        else:
            return queryset

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
    ) -> type['JSONFieldFilter']:
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
