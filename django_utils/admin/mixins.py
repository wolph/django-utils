"""Opt-in ``ModelAdmin`` mixins.

``ReadOnlyModelAdminMixin`` turns any existing admin — including one
using this package's filters and widgets — into a safe read-only view:
add/change/delete are denied for everyone (superusers included), every
concrete field and many-to-many relation becomes read-only, and the
list configuration
(``list_display``, ``list_filter``, ``search_fields``) keeps working
untouched.  Built exclusively on stable public ``ModelAdmin`` API.

``CountColumnMixin`` adds sortable ``list_display`` columns for related
object counts (``count_columns = ('review',)`` gives a ``review_count``
column), annotated via ``django_utils.aggregates.SubqueryCount`` so
combining several relations never fans out through a JOIN.
"""

import typing
from typing import TYPE_CHECKING

from django import http

from django_utils import aggregates


class ReadOnlyModelAdminMixin:
    """Deny add/change/delete; make every field read-only.

    Governs the *parent* admin's own permissions only: an editable
    ``inlines`` entry on the wrapped admin is not made read-only by
    this mixin. Django still denies the inline's add/change/delete POST
    (each inline formset checks its own model's permissions
    independently), so nothing is actually editable through it -- but
    the change-form UI still renders its widgets as if it were, which
    can mislead a user into thinking edits are possible. Apply this
    mixin to inline admin classes too if you want their rendered UI to
    match.
    """

    if TYPE_CHECKING:
        # Provided by the ModelAdmin this is mixed into.
        model: typing.Any

    def has_add_permission(self, request: http.HttpRequest) -> bool:
        return False

    def has_change_permission(
        self,
        request: http.HttpRequest,
        obj: typing.Any = None,
    ) -> bool:
        return False

    def has_delete_permission(
        self,
        request: http.HttpRequest,
        obj: typing.Any = None,
    ) -> bool:
        return False

    def get_readonly_fields(
        self,
        request: http.HttpRequest,
        obj: typing.Any = None,
    ) -> tuple[str, ...]:
        # Merge with, don't replace, whatever the wrapped admin already
        # declares. An admin using the ordinary `fields = (...,
        # 'shouting_name')` / `readonly_fields = ('shouting_name',)` /
        # `shouting_name()` method pattern is fine on its own; replacing
        # its `readonly_fields` outright used to drop `shouting_name`
        # from both `form.base_fields` (excluded because it was declared
        # readonly) and the returned `readonly_fields` (recomputed here
        # from concrete/M2M fields only, which a plain method-backed
        # display attribute is neither) -- present in the fieldset but
        # in neither collection, the same `KeyError` crash class as the
        # M2M bug fixed above. `dict.fromkeys()` dedupes while
        # preserving first-seen order (the wrapped admin's own entries,
        # then the model's fields).
        meta = self.model._meta
        model_fields = (
            field.name for field in (*meta.concrete_fields, *meta.many_to_many)
        )
        return tuple(
            dict.fromkeys(
                (
                    *super().get_readonly_fields(  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
                        request, obj
                    ),
                    *model_fields,
                )
            )
        )


def _count_column_method(
    column: str, relation: str
) -> 'typing.Callable[[typing.Any], typing.Any]':
    def method(obj: typing.Any) -> typing.Any:
        return getattr(obj, column)

    method.short_description = (  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
        f'{relation.replace("_", " ")} count'
    )
    method.admin_order_field = column  # type: ignore[attr-defined]  # ty: ignore[unresolved-attribute]
    return method


class CountColumnMixin:
    """Sortable related-object count columns, without JOIN fan-out."""

    count_columns: tuple[str, ...] = ()

    if TYPE_CHECKING:
        model: typing.Any

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        for relation in self.count_columns:
            column = f'{relation}_count'
            if not hasattr(self, column):
                setattr(self, column, _count_column_method(column, relation))

    def get_queryset(self, request: http.HttpRequest) -> 'typing.Any':
        queryset = super().get_queryset(request)  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
        return queryset.annotate(
            **{
                f'{relation}_count': aggregates.SubqueryCount(relation)
                for relation in self.count_columns
            }
        )

    def get_list_display(
        self, request: http.HttpRequest
    ) -> 'tuple[typing.Any, ...]':
        display = list(super().get_list_display(request))  # type: ignore[misc]  # ty: ignore[unresolved-attribute]
        for relation in self.count_columns:
            column = f'{relation}_count'
            if column not in display:
                display.append(column)
        return tuple(display)
