# Django Utils

[![CI](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml/badge.svg)](https://github.com/WoLpH/django-utils/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Python versions](https://img.shields.io/pypi/pyversions/django-utils2.svg)](https://pypi.org/project/django-utils2/)
[![Documentation](https://readthedocs.org/projects/django-utils-2/badge/?version=latest)](https://django-utils-2.readthedocs.io/en/latest/)

![The data__filling dropdown filter open in the Django admin sidebar, listing Avocado, Bacon, Cheddar, Corned Beef and Turkey](https://raw.githubusercontent.com/WoLpH/django-utils/master/docs/_static/screenshots/filters-sidebar.png)

Django Utils is a collection of small Django helpers, admin power-ups and ORM
utilities that make common patterns shorter, safer, and ASGI-friendly —
JSON-aware admin filters and a validating JSON widget, collision-free slug
mixins and metadata-carrying choices, encrypted model fields, a native
PostgreSQL enum field, memory-bounded queryset iteration and fan-out-safe
subquery aggregates, chunked management commands, contextvars-based request
context, and header-based CSRF hardening. It builds on the
[Python Utils](https://github.com/WoLpH/python-utils) library, is by no
means a complete collection, but has served production projects well and
keeps growing.

Full documentation, including a "why this over the alternatives" page, is
at <https://django-utils-2.readthedocs.io/en/latest/>.

## Requirements

- Python 3.10+
- Django 4.2, 5.2, or 6.0

## Install

1. Run `pip install django-utils2`
2. Add `django_utils` to your `INSTALLED_APPS`

If you want to run the tests, install the `tests` extra
(`pip install "django-utils2[tests]"`) and run `pytest`.

## Quickstart

Filter an admin changelist on a nested `JSONField` value — no custom
`SimpleListFilter` needed:

```python
from django.contrib import admin
from django_utils.admin.filters import JSONFieldFilterDropdown

from myapp.models import Sandwich


class SandwichAdmin(admin.ModelAdmin):
    list_filter = (
        JSONFieldFilterDropdown.create('data__filling'),
    )


admin.site.register(Sandwich, SandwichAdmin)
```

A sidebar filter on `data['filling']`, no JOIN or denormalized column. See
the [quickstart](https://django-utils-2.readthedocs.io/en/latest/quickstart.html)
page for two more 2-minute wins.

## Features

Every feature below has its own page on the docs site, with runnable
examples, edge cases, and (for the admin features) screenshots or a live
in-browser demo.

- **Admin dropdown / Select2 / JSON filters** — dropdown, autocomplete, and
  JSON sub-path list filters for the changelist sidebar, plus an operator
  selector (`gte`, `lte`, `icontains`, ...) for typed comparisons. See
  [Select / dropdown / autocomplete filters](https://django-utils-2.readthedocs.io/en/latest/admin.html#dropdown-filters)
  and [Operator filters](https://django-utils-2.readthedocs.io/en/latest/admin.html#operator-filters).
- **JSON widget** — a drop-in `JSONField` admin widget that pretty-prints
  and validates JSON as you type. See
  [JSON widget](https://django-utils-2.readthedocs.io/en/latest/admin.html#json-widget-section).
- **Read-only admin** — turn any `ModelAdmin` into a read-only view:
  add/change/delete denied for everyone, filtering and search still work.
  See [Read-only admin](https://django-utils-2.readthedocs.io/en/latest/admin.html#read-only-admin).
- **Count columns** — sortable related-object count columns for
  `list_display`, without the N+1 or JOIN fan-out footguns. See
  [Count columns](https://django-utils-2.readthedocs.io/en/latest/admin.html#count-columns).
- **Admin export** — streaming CSV/JSON export actions for the changelist,
  memory-bounded via `queryset_iterator`. See
  [Export](https://django-utils-2.readthedocs.io/en/latest/admin.html#admin-export).
- **Choices** — metadata-carrying choices with dict-like access and a real
  `enum.Enum` on demand via `as_enum()`. See
  [Choices](https://django-utils-2.readthedocs.io/en/latest/models-fields.html#choices).
- **PostgreSQL ENUM field** — a `CharField` backed by a native PostgreSQL
  `ENUM` type on Postgres, plain `VARCHAR` everywhere else, with
  hand-written migration operations for creating the type and adding
  values. See
  [PostgreSQL ENUM field](https://django-utils-2.readthedocs.io/en/latest/models-fields.html#postgresql-enum-field).
- **Request/user context (ASGI-safe)** — access the current request/user
  from anywhere via `contextvars`, isolated per asyncio task, unlike
  thread-local equivalents. See
  [Current request / user (ASGI-safe)](https://django-utils-2.readthedocs.io/en/latest/middleware.html#current-request-user-asgi-safe).
- **Query budgets** — catch N+1 regressions in production code paths, not
  just in tests, with a query-counting context manager/decorator. See
  [Query budgets](https://django-utils-2.readthedocs.io/en/latest/middleware.html#query-budgets).
- **Auth helpers** — `superuser_required`/`staff_required` decorators and a
  `permission_string()` builder for `has_perm()` checks. See
  [Auth helpers](https://django-utils-2.readthedocs.io/en/latest/middleware.html#auth-helpers).
- **Fetch-Metadata CSRF middleware** — defense-in-depth CSRF hardening
  using the `Sec-Fetch-Site` header, run alongside (not instead of)
  Django's own CSRF middleware. See
  [Fetch-Metadata CSRF middleware](https://django-utils-2.readthedocs.io/en/latest/middleware.html#fetch-metadata-csrf-middleware).
- **Subquery aggregates** — `SubqueryCount`/`SubquerySum`/`SubqueryAvg`/...
  annotate each aggregate in its own subquery, avoiding the JOIN fan-out
  that multiplies counts. See
  [Subquery aggregates](https://django-utils-2.readthedocs.io/en/latest/querysets.html#subquery-aggregates).
- **Bulk upsert** — `bulk_update_or_create()`: one
  `INSERT ... ON CONFLICT DO UPDATE` batch instead of a racy,
  two-query-per-row loop. See
  [Bulk upsert](https://django-utils-2.readthedocs.io/en/latest/querysets.html#bulk-upsert).
- **Chunked management commands** — `ChunkedCommand`: memory-bounded,
  resumable processing of large querysets with progress logging and a
  transactional dry-run. See
  [ChunkedCommand](https://django-utils-2.readthedocs.io/en/latest/commands.html#chunkedcommand).
- **Encrypted model fields** — `EncryptedCharField`/`EncryptedTextField`/
  `EncryptedJSONField`: Fernet-encrypted values in a plain `TEXT` column,
  with key-rotation support. See
  [Encrypted model fields](https://django-utils-2.readthedocs.io/en/latest/models-fields.html#encrypted-model-fields).

## Links

- Documentation: <https://django-utils-2.readthedocs.io/en/latest/>
- Source: <https://github.com/WoLpH/django-utils>
- Bug reports: <https://github.com/WoLpH/django-utils/issues>
- Package homepage: <https://pypi.org/project/django-utils2/>
- My blog: <http://w.wol.ph/>
