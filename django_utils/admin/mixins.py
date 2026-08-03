"""Opt-in ``ModelAdmin`` mixins.

``ReadOnlyModelAdminMixin`` turns any existing admin — including one
using this package's filters and widgets — into a safe read-only view:
add/change/delete are denied for everyone (superusers included), every
concrete field becomes read-only, and the list configuration
(``list_display``, ``list_filter``, ``search_fields``) keeps working
untouched.  Built exclusively on stable public ``ModelAdmin`` API.
"""

import typing

from django import http


class ReadOnlyModelAdminMixin:
    """Deny add/change/delete; make every field read-only."""

    if typing.TYPE_CHECKING:
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
        return tuple(field.name for field in self.model._meta.concrete_fields)
