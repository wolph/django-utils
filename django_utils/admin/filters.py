import typing
from abc import ABC
from datetime import timedelta

from django import http
from django.contrib import admin
from django.contrib.admin import widgets
from django.contrib.admin.filters import AllValuesFieldListFilter
from django.contrib.admin.filters import BooleanFieldListFilter
from django.contrib.admin.filters import ChoicesFieldListFilter
from django.contrib.admin.filters import DateFieldListFilter
from django.contrib.admin.filters import FieldListFilter
from django.contrib.admin.filters import ListFilter
from django.contrib.admin.filters import RelatedFieldListFilter
from django.contrib.admin.filters import RelatedOnlyFieldListFilter
from django.contrib.admin.filters import SimpleListFilter
from django.core.cache import cache
from django.db import models

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

from django.utils import text

CACHE_TIMEOUT = timedelta(minutes=10)


class DropdownMixin:
    template = 'django_utils/admin/dropdown_filter.html'


class Select2Mixin:
    template = 'django_utils/admin/select2_filter.html'

    def select_html_id(self):
        return text.slugify(self.title)

    # Quick hack to re-use the admin select2 files
    Media = widgets.AutocompleteMixin(None, None).media


class FilterBase(admin.SimpleListFilter):
    timeout: timedelta = None

    def get_lookups_cache_timeout(self):
        timeout = self.timeout or CACHE_TIMEOUT
        if timeout:
            return timeout.total_seconds()

    def get_lookups_cache_key(self, request: http.HttpRequest):
        return request.get_full_path() + self.title

    def set_lookups_cache(self, request: http.HttpRequest, lookups):
        timeout = self.get_lookups_cache_timeout()
        if timeout:
            cache.set(self.get_lookups_cache_key(request), lookups, timeout)

    def get_lookups_cache(self, request: http.HttpRequest):
        return cache.get(self.get_lookups_cache_key(request))

    def formatter(self, value):
        '''Formatter to convert the value in human readable output'''
        return str(value).title()


class JSONFieldFilter(FilterBase):
    field_path = None

    @staticmethod
    def cast(value):
        return value

    @property
    def attribute_path(self):
        return self.field_path.split('__', 1)[1]

    def lookups(self, request, model_admin):
        '''The list of value/label pairs for the filter bar with caching'''
        assert self.field_path, '`field_path` is required'

        cache = self.get_lookups_cache(request)
        if cache:
            return cache

        values = model_admin.model.objects.values_list(
            self.field_path, flat=True,
        ).order_by(self.field_path).distinct()

        lookups = [(value, self.formatter(value)) for value in values]
        self.set_lookups_cache(request, lookups)

        return lookups

    def queryset(self, request: http.HttpRequest, queryset: models.QuerySet) \
            -> models.QuerySet:
        value = self.value()
        if value:
            return queryset.filter(**{self.field_path: self.cast(value)})
        else:
            return queryset

    @classmethod
    def create(cls,
               field_path: str,
               title: str = None,
               parameter_name: str = None,
               template: str = None,
               formatter: typing.Callable[[typing.Any], str] = None,
               cast: typing.Callable[[str], typing.Any] = None,
               timeout: timedelta = None) -> typing.Type['JSONFieldFilter']:

        class Filter(cls):
            pass

        assert '__' in field_path, 'Paths require both the field and parameter'
        Filter.field_path = field_path
        Filter.title = title or (' '.join(field_path.split('_'))).title()
        Filter.parameter_name = parameter_name or field_path
        Filter.timeout = timeout

        if formatter:
            Filter.formatter = formatter

        if template:
            Filter.template = template

        if cast:
            Filter.cast = cast

        return Filter


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


class RelatedOnlyFieldListFilterSelect2(Select2Mixin,
                                        RelatedOnlyFieldListFilter):
    pass


class JSONFieldFilterDropdown(DropdownMixin, JSONFieldFilter):
    pass


class SimpleListFilterDropdown(DropdownMixin, SimpleListFilter, ABC):
    pass


class AllValuesFieldListFilterDropdown(DropdownMixin,
                                       AllValuesFieldListFilter):
    pass


class ChoicesFieldListFilterDropdown(DropdownMixin, ChoicesFieldListFilter):
    pass


class RelatedFieldListFilterDropdown(DropdownMixin, RelatedFieldListFilter):
    pass


class RelatedOnlyFieldListFilterDropdown(DropdownMixin,
                                         RelatedOnlyFieldListFilter):
    pass
