# Django Utils

[![CI](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Documentation](https://readthedocs.org/projects/django-utils-2/badge/?version=latest)](https://django-utils-2.readthedocs.io/en/latest/)

Django Utils is a collection of the small Django helpers, admin
power-ups and ORM utilities that most projects end up writing
themselves: JSON-aware admin filters, encrypted model fields,
memory-bounded queryset iteration, resumable management commands, and
more. It is by no means a complete collection, but it has served
production projects well and keeps growing.

::::{grid} 1 2 2 3
:gutter: 3

:::{grid-item-card} Admin power-ups
:link: admin
:link-type: doc

Filters (including JSON sub-path and operator filters), the validating
JSON widget, read-only admin, sortable count columns, and CSV/JSON export.
:::

:::{grid-item-card} Models & fields
:link: models-fields
:link-type: doc

Slug/`__str__` mixins, metadata-carrying choices, Fernet-encrypted fields,
and a native PostgreSQL enum field.
:::

:::{grid-item-card} QuerySets & bulk
:link: querysets
:link-type: doc

Memory-bounded `queryset_iterator`, fan-out-safe subquery aggregates, and
chunked upsert via `bulk_update_or_create`.
:::

:::{grid-item-card} Management commands
:link: commands
:link-type: doc

`ChunkedCommand`: resumable, checkpointed processing of large querysets
with progress logging and a transactional dry-run.
:::

:::{grid-item-card} Middleware & context
:link: middleware
:link-type: doc

ASGI-safe request/user context, Fetch-Metadata CSRF hardening, auth
decorators, and production-safe query budgets.
:::

:::{grid-item-card} Why django-utils2
:link: why
:link-type: doc

What it does differently from django-extensions and django-model-utils,
and the quality gates every release has to pass.
:::
::::

## Quickstart

```bash
pip install django-utils2
```

```python
INSTALLED_APPS = [
    ...,
    'django_utils',
]
```

The [quickstart](quickstart.md) walks through the first three features
worth enabling.

```{toctree}
:hidden:

quickstart
why
admin
models-fields
querysets
commands
middleware
changelog
django_utils
```

```{toctree}
:hidden:
:caption: Live demos

demos/json-widget
demos/dropdown-filter
```
