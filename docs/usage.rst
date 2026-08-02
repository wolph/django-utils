Usage
=====

Django Utils is a collection of small Django helper functions, utilities and
classes which make common patterns shorter and easier.

Installation
------------

Install with pip::

    pip install django-utils2

Add ``django_utils`` to your ``INSTALLED_APPS``.

Admin Select / Dropdown / Autocomplete (JSON) Filters
------------------------------------------------------

All of the standard admin list filters are available through
``django_utils.admin.filters`` as:

- The original filter (e.g. ``SimpleListFilter``)
- A basic select/dropdown filter: ``SimpleListFilterDropdown``
- A select2 based autocompleting dropdown filter: ``SimpleListFilterSelect2``

On PostgreSQL you can additionally filter on JSON fields as well given
paths::

    class SomeModelAdmin(admin.ModelAdmin):
        list_filter = (
            JSONFieldFilterSelect2.create('some_json_field__some__sub_path'),
        )

Operator filters
~~~~~~~~~~~~~~~~~

``JSONFieldFilter.create()`` accepts an ``operators`` keyword that adds
an operator selector (read from ``<parameter_name>__op`` in the query
string) alongside the value::

    class SomeModelAdmin(admin.ModelAdmin):
        list_filter = (
            JSONFieldFilter.create(
                'data__price', operators=('gte',), cast=int
            ),
        )

Supported operators are ``exact``, ``contains``, ``icontains``,
``startswith``, ``gt``, ``gte``, ``lt``, ``lte`` and ``range``. An
operator submitted outside this allowlist raises ``SuspiciousOperation``
rather than reaching the ORM.

``contains`` and ``range`` are rejected at ``create()`` time for JSON
sub-paths, with a ``ValueError`` explaining why:

- ``contains`` on a JSON sub-path (a ``KeyTransform``) resolves to
  PostgreSQL's ``@>`` containment lookup, not substring matching, and
  raises ``NotSupportedError`` on SQLite. Use ``icontains`` for substring
  matching instead.
- ``range`` expects a two-element sequence, but a filter only ever
  supplies one scalar value from the query string.

``gt``, ``gte``, ``lt``, ``lte`` and ``range`` compare numerically, so
``create()`` requires a ``cast`` (e.g. ``cast=int``) whenever one of them
is listed. Omitting ``operators`` entirely leaves a filter's behaviour
unchanged -- it still defaults to ``exact``.

For a free-text value paired with the operator dropdown -- a better fit
than the default choices list for a ``gte``/``lte`` filter on a field with
too many distinct values to enumerate -- pass
``template='django_utils/admin/lookup_filter.html'`` to ``create()``.

JSON widget
-----------

:py:class:`django_utils.admin.widgets.JSONWidget` is a drop-in
replacement for the admin's default ``JSONField`` textarea. Django
renders a stored value on one line (``{"b": 2, "a": [1, 2]}``) and only
reports a parse error after a submit round-trip. ``JSONWidget`` indents
and key-sorts the value, and validates it as you type, via a small,
CSP-safe vanilla-JS asset (no inline handlers, no ``eval``) that degrades
to a plain textarea if JavaScript is unavailable.

Django already preserves malformed JSON input across the round-trip
(``forms.JSONField.bound_data()`` returns it as ``InvalidJSONInput``
instead of discarding it) -- ``JSONWidget`` does not change that
behaviour. What it adds is pretty-printing of well-formed values and
inline validation feedback.

Enable it per ``ModelAdmin`` with
:py:class:`~django_utils.admin.widgets.JSONWidgetMixin`::

    from django_utils.admin.widgets import JSONWidgetMixin


    class SomeModelAdmin(JSONWidgetMixin, admin.ModelAdmin):
        pass

Nothing is patched globally -- a project that only uses this package for
the filters above sees no change to its ``JSONField`` forms.

Choices usage
-------------

Django 3.0+ ships native ``models.TextChoices`` / ``models.IntegerChoices``
enums; ``django_utils.choices`` remains for the extra ``Choice`` metadata and
dict-like access it provides::

    from django_utils import choices


    class Human(models.Model):
        class Gender(choices.Choices):
            MALE = 'm'
            FEMALE = 'f'
            OTHER = 'o'

        gender = models.CharField(max_length=1, choices=Gender)

See the `project README
<https://github.com/WoLpH/django-utils/blob/master/README.md>`_ for the
full usage guide.
