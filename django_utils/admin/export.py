"""Streaming CSV/JSON export actions for the admin.

Dependency-free (stdlib ``csv``/``json``), streaming
(``StreamingHttpResponse`` + ``queryset_iterator``, so a million-row
export never materialises in memory), and scoped on purpose: CSV and
JSON only, export only.  For XLSX, import flows, resource classes and
the rest, use django-import-export -- this module exists for the 90%
case without its weight.

CSV injection: spreadsheet applications execute cell values starting
with ``=``, ``+``, ``-`` or ``@`` as formulas.  Exported text values
starting with those characters are prefixed with a single quote
(documented OWASP mitigation); numbers and other non-str values are
left untouched.

Both actions run against the queryset the changelist hands them --
already narrowed by ``list_filter``, search, and this package's own
admin filters (:mod:`django_utils.admin.filters`) -- so the intended
flow is filter first, select second, export third: the export never
sees a row the changelist wouldn't have shown.
"""

import csv
import json
import typing
from typing import TYPE_CHECKING

from django import http
from django.contrib import admin

from django_utils import queryset as queryset_module

if TYPE_CHECKING:
    from collections.abc import Generator

    from django.db.models import QuerySet

# Not exposed as a public option: nothing in the design calls for a
# configurable chunk size, but naming the default lets tests exercise
# multi-chunk streaming (monkeypatch this) without guessing at
# `queryset_iterator`'s own default.
_CHUNK_SIZE = 1000

_DANGEROUS_PREFIXES = ('=', '+', '-', '@')


class _Echo:
    """File-like object whose ``write`` returns its argument instead of
    writing it anywhere.

    Handing this to :class:`csv.writer` turns every ``writerow()`` call
    into the formatted CSV line as a return value, which the caller
    yields straight into ``StreamingHttpResponse`` -- no buffer, in
    memory or otherwise, ever holds more than one row.
    """

    def write(self, value: str) -> str:
        return value


def _export_fields(model_admin: typing.Any) -> tuple[str, ...]:
    """Columns to export: ``model_admin.export_fields`` if set,
    otherwise every concrete field's attname (so foreign keys export
    as ``<name>_id`` values, not related objects)."""
    export_fields = getattr(model_admin, 'export_fields', None)
    if export_fields:
        return tuple(export_fields)
    meta = model_admin.model._meta
    return tuple(field.attname for field in meta.concrete_fields)


def _guard_csv(value: typing.Any) -> typing.Any:
    """Prefix a leading ``=``, ``+``, ``-`` or ``@`` in string values
    with a single quote -- the documented OWASP mitigation for CSV
    injection. Non-str values (ints, Decimals, dates, ...) are
    returned untouched."""
    if isinstance(value, str) and value.startswith(_DANGEROUS_PREFIXES):
        return f"'{value}"
    return value


def _attachment_filename(model_admin: typing.Any, extension: str) -> str:
    model_name = model_admin.model._meta.model_name
    return f'{model_name}_export.{extension}'


def _content_disposition(filename: str) -> str:
    return f'attachment; filename="{filename}"'


class ExportMixin:
    """Adds ``export_as_csv``/``export_as_json`` admin actions.

    Both stream via ``StreamingHttpResponse``: rows are pulled one at
    a time from ``django_utils.queryset.queryset_iterator``, so
    exporting a million rows never materialises the table in memory.
    They run against whatever queryset the changelist hands them --
    see the module docstring for the filter-then-export composition
    story.

    ``export_fields`` picks the exported columns; left unset, it
    defaults to every concrete field's attname (``tuple(f.attname for
    f in model._meta.concrete_fields)``), so foreign keys export as
    ``<name>_id`` values rather than related objects::

        class IngredientAdmin(ExportMixin, admin.ModelAdmin):
            export_fields = ('name', 'stock')

    ``actions = ('export_as_csv', 'export_as_json')`` is a plain class
    attribute here, picked up by ``ModelAdmin``'s default
    ``get_actions()`` -- nothing to override. An admin that declares
    its own ``actions`` list replaces this one outright (Python
    attribute lookup, not a merge), so include both names in it::

        class IngredientAdmin(ExportMixin, admin.ModelAdmin):
            actions = ('export_as_csv', 'export_as_json', 'my_action')
    """

    actions = ('export_as_csv', 'export_as_json')
    export_fields: tuple[str, ...] | None = None

    if TYPE_CHECKING:
        model: typing.Any

    @admin.action(description='Export selected as CSV')
    def export_as_csv(
        self, request: http.HttpRequest, queryset: 'QuerySet[typing.Any]'
    ) -> http.StreamingHttpResponse:
        fields = _export_fields(self)

        def rows() -> 'Generator[str, None, None]':
            writer = csv.writer(_Echo())
            yield writer.writerow(fields)
            for obj in queryset_module.queryset_iterator(
                queryset, chunksize=_CHUNK_SIZE
            ):
                yield writer.writerow(
                    _guard_csv(getattr(obj, field)) for field in fields
                )

        response = http.StreamingHttpResponse(rows(), content_type='text/csv')
        filename = _attachment_filename(self, 'csv')
        response['Content-Disposition'] = _content_disposition(filename)
        return response

    @admin.action(description='Export selected as JSON')
    def export_as_json(
        self, request: http.HttpRequest, queryset: 'QuerySet[typing.Any]'
    ) -> http.StreamingHttpResponse:
        fields = _export_fields(self)

        def rows() -> 'Generator[str, None, None]':
            yield '['
            separator = ''
            for obj in queryset_module.queryset_iterator(
                queryset, chunksize=_CHUNK_SIZE
            ):
                row = {field: getattr(obj, field) for field in fields}
                yield f'{separator}{json.dumps(row, default=str)}'
                separator = ','
            yield ']'

        response = http.StreamingHttpResponse(
            rows(), content_type='application/json'
        )
        filename = _attachment_filename(self, 'json')
        response['Content-Disposition'] = _content_disposition(filename)
        return response
