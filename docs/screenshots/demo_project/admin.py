"""Admin registrations for the screenshot demo project.

Only registers admins for behaviour the docs screenshots need that
`tests.test_app.admin` doesn't already provide. That module is
auto-discovered too -- `tests.test_app` is installed here for its
models -- and already registers `Ingredient` with `ExportMixin`
(`export-actions.png` reuses that registration), plus `Spam`, `Eggs`
and `RecursionTest` (unused by any screenshot here). A second
`admin.site.register(Ingredient, ...)` call would raise
`AlreadyRegistered`, so this module registers `Sandwich` and `Tag`
only -- both untouched by `tests.test_app.admin`.
"""

import typing

from django.contrib import admin
from django_utils.admin import filters
from django_utils.admin.mixins import CountColumnMixin, ReadOnlyModelAdminMixin
from django_utils.admin.widgets import JSONWidgetMixin
from tests.test_app import models


class SandwichAdmin(JSONWidgetMixin, CountColumnMixin, admin.ModelAdmin):
    """Backs `filters-sidebar.png`, `operator-filter.png`,
    `json-widget.png` and `count-columns.png`: one admin, four
    screenshots of four different query states / views of it."""

    list_display = ('id', 'filling', 'price')
    count_columns = ('review', 'topping')
    list_filter = (
        filters.JSONFieldFilterDropdown.create('data__filling'),
        filters.JSONFieldFilter.create(
            'data__price',
            operators=('gte', 'lte'),
            cast=int,
            template='django_utils/admin/lookup_filter.html',
        ),
    )

    @admin.display(description='filling')
    def filling(self, obj: typing.Any) -> str:
        return obj.data.get('filling', '')

    @admin.display(description='price')
    def price(self, obj: typing.Any) -> str:
        return obj.data.get('price', '')


class TagAdmin(ReadOnlyModelAdminMixin, admin.ModelAdmin):
    """Backs `readonly-admin.png`: `name` and the `sandwiches`
    many-to-many both render read-only."""

    list_display = ('id', 'name')


admin.site.register(models.Sandwich, SandwichAdmin)
admin.site.register(models.Tag, TagAdmin)
