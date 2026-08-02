"""Admin widgets for working with :py:class:`~django.db.models.JSONField`."""

from __future__ import annotations

import json
from typing import Any, ClassVar

from django import forms
from django.db import models


class JSONWidget(forms.Textarea):
    """A ``JSONField`` textarea that pretty-prints and validates client-side.

    Django renders a stored value on a single line
    (``{"b": 2, "a": [1, 2]}``) and reports parse errors only after a
    submit round-trip. This widget indents and key-sorts the value, and
    reports parse errors inline as you type.

    Malformed input is *not* reformatted: Django already round-trips it
    through ``InvalidJSONInput`` and that behaviour is preserved here.
    """

    class Media:
        js: ClassVar[list[str]] = ['django_utils/admin/json_widget.js']
        css: ClassVar[dict[str, list[str]]] = {
            'all': ['django_utils/admin/json_widget.css']
        }

    def __init__(self, attrs: dict[str, Any] | None = None) -> None:
        defaults: dict[str, Any] = {'data-json-widget': True}
        if attrs:
            defaults.update(attrs)
        super().__init__(defaults)

    def format_value(self, value: Any) -> Any:
        formatted = super().format_value(value)
        if not isinstance(formatted, str):
            return formatted

        try:
            parsed = json.loads(formatted)
        except (TypeError, ValueError):
            # Malformed input: hand it back untouched so Django's
            # InvalidJSONInput round-trip keeps working.
            return formatted

        return json.dumps(parsed, indent=2, sort_keys=True, ensure_ascii=False)


class JSONWidgetMixin:
    """Opt a ``ModelAdmin`` into :py:class:`JSONWidget` for its JSON fields.

    .. code-block:: python

        class MyAdmin(JSONWidgetMixin, admin.ModelAdmin):
            pass

    Nothing is patched globally: a project that installs this package for
    the filters alone sees no change to its forms.
    """

    formfield_overrides: ClassVar[dict[type[models.Field[Any, Any]], Any]] = {
        models.JSONField: {'widget': JSONWidget},
    }
