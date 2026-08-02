# Django Utils

[![CI](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Documentation](https://readthedocs.org/projects/django-utils-2/badge/?version=latest)](https://django-utils-2.readthedocs.io/en/latest/)

Django Utils is a collection of small Django helper functions, utilities and
classes which make common patterns shorter and easier. It is by no means a
complete collection but it has served me quite a bit in the past and I will
keep extending it.

Examples are:

- Admin Select (Dropdown) filters
- Admin Select2 (Autocomplete dropdown) filters
- Admin JSON sub-field filters
- Enum based choicefields that can carry arbitrary metadata and convert to a
  real `enum.Enum` on demand
- Models with automatic `__str__`, `__unicode__` and `__repr__` functions
  based on names and/or slugs using simple mixins.
- Models with automatic `updated_at` and `created_at` fields
- Models with automatic, collision-free slugs based on the `name` property.
- Iterating through querysets in predefined chunks to prevent out of memory
  errors, bounding memory on both the client and the database server, and
  friendly to distribution across read replicas

The library depends on the Python Utils library.

Documentation is available at: <https://django-utils-2.readthedocs.io/en/latest/>

## Requirements

- Python 3.10+
- Django 4.2, 5.2, or 6.0

## Install

To install:

1. Run `pip install django-utils2`
2. Add `django_utils` to your `INSTALLED_APPS`

If you want to run the tests, install the `tests` extra
(`pip install "django-utils2[tests]"`) and run `pytest`.

## Admin Select / Dropdown / Autocomplete (JSON) Filters

All of the standard admin list filters are available through
`django_utils.admin.filters` as:

- The original filter (e.g. `SimpleListFilter`)
- A basic select/dropdown filter: `SimpleListFilterDropdown`
- A select2 based autocompleting dropdown filter: `SimpleListFilterSelect2`

On PostgreSQL you can additionally filter on JSON fields as well given paths:

```python
class SomeModelAdmin(admin.ModelAdmin):
    list_filter = (
        JSONFieldFilterSelect2.create('some_json_field__some__sub_path'),
    )
```

That will filter a JSON field named `some_json_field` and look for values
like this:

```json
{"some": {"sub_path": "some value"}}
```

By default the results for the JSON filters are cached for 10 minutes but
can be changed through the `create` parameters.

### Operator filters

`JSONFieldFilter.create()` accepts an `operators` keyword that adds an
operator selector (rendered from `<parameter_name>__op` in the query
string) alongside the value:

```python
class SomeModelAdmin(admin.ModelAdmin):
    list_filter = (
        JSONFieldFilter.create(
            'data__price', operators=('gte',), cast=int
        ),
    )
```

Supported operators are `exact`, `contains`, `icontains`, `startswith`,
`gt`, `gte`, `lt`, `lte` and `range`. An operator submitted outside this
allowlist raises `SuspiciousOperation` rather than reaching the ORM.

Two operators are rejected at `create()` time for JSON sub-paths, with a
`ValueError` explaining why:

- `contains` -- on a JSON sub-path (a `KeyTransform`) this resolves to
  PostgreSQL's `@>` containment lookup, not substring matching, and raises
  `NotSupportedError` on SQLite. Use `icontains` for substring matching.
- `range` -- expects a two-element sequence, but a filter only ever
  supplies one scalar value from the query string.

`gt`, `gte`, `lt`, `lte` and `range` compare numerically, so `create()`
requires a `cast` (e.g. `cast=int`) whenever one of them is listed;
omitting it is a configuration error caught immediately rather than a
string comparison bug found later. Omitting `operators` entirely leaves a
filter's behaviour unchanged -- it still defaults to `exact`.

The default filter sidebar renders an operator-aware filter as a list of
distinct values, same as any other filter. For a free-text value paired
with the operator dropdown -- the better fit for `gte`/`lte` filters on a
field with too many distinct values to list -- pass
`template='django_utils/admin/lookup_filter.html'`:

```python
JSONFieldFilter.create(
    'data__price',
    operators=('gte', 'lte'),
    cast=int,
    template='django_utils/admin/lookup_filter.html',
)
```

## JSON widget

`django_utils.admin.widgets.JSONWidget` is a drop-in replacement for the
admin's default `JSONField` textarea. Django renders a stored value on one
line (`{"b": 2, "a": [1, 2]}`) and only reports a parse error after a
submit round-trip. `JSONWidget` indents and key-sorts the value, and
validates it as you type, via a small, CSP-safe vanilla-JS asset (no
inline handlers, no `eval`) that degrades to a plain textarea if
JavaScript is unavailable.

Django already preserves malformed JSON input across the round-trip
(`forms.JSONField.bound_data()` returns it as `InvalidJSONInput` instead
of discarding it) -- `JSONWidget` does not change that behaviour. What it
adds is pretty-printing of well-formed values and inline validation
feedback; it does not touch how malformed input is stored or redisplayed.

Enable it per `ModelAdmin` with `JSONWidgetMixin`:

```python
from django_utils.admin.widgets import JSONWidgetMixin


class SomeModelAdmin(JSONWidgetMixin, admin.ModelAdmin):
    pass
```

Nothing is patched globally -- a project that only uses this package for
the filters above sees no change to its `JSONField` forms.

## Choices usage

To enable easy to use choices which are more convenient than the Django 3.0
choices system you can use this:

Django 3.0+ ships native `models.TextChoices` / `models.IntegerChoices`
enums; `django_utils.choices` remains for the extra `Choice` metadata and
dict-like access it provides.

```python
from django_utils import choices


# For manually specifying the value (automatically detects `str`, `int` and `float`):
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = 'm'
        FEMALE = 'f'
        OTHER = 'o'

    gender = models.CharField(max_length=1, choices=Gender)


# To define the values as `male` implicitly:
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = choices.Choice()
        FEMALE = choices.Choice()
        OTHER = choices.Choice()

    gender = models.CharField(max_length=1, choices=Gender)


# Or explicitly define them
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = choices.Choice('m', 'male')
        FEMALE = choices.Choice('f', 'female')
        OTHER = choices.Choice('o', 'other')

    gender = models.CharField(max_length=1, choices=Gender)
```

`Choice` also accepts arbitrary keyword metadata, reachable as attributes on
the resolved choice, and `Choices.as_enum()` builds a real `enum.Enum` from
the class without touching the original (so model fields keep using the
raw-value class while application code gets `isinstance`/`match` support):

```python
class Status(choices.Choices):
    ACTIVE = choices.Choice('a', 'Active', color='green')
    INACTIVE = choices.Choice('i', 'Inactive', color='red')


Status.choices['a'].color  # 'green'

StatusEnum = Status.as_enum()
StatusEnum('a') is StatusEnum.ACTIVE  # True
```

A PostgreSQL ENUM field will be coming soon to automatically facilitate the
creation of the enum if needed.

## Links

- Documentation: <https://django-utils-2.readthedocs.io/en/latest/>
- Source: <https://github.com/WoLpH/django-utils>
- Bug reports: <https://github.com/WoLpH/django-utils/issues>
- Package homepage: <https://pypi.org/project/django-utils2/>
- My blog: <http://w.wol.ph/>
