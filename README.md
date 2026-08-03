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

`create(operators=...)` itself accepts `exact`, `contains`, `icontains`,
`startswith`, `gt`, `gte`, `lt`, `lte` and `range`; passing anything
outside that fixed list raises `ValueError` at `create()` time. At
request time, the operator actually submitted in the query string is
checked against *this filter's own* `operators` -- the subset you passed
to `create()`, default `('exact',)` -- not the full list above, so a
generally-valid operator this particular filter never declared still
raises `SuspiciousOperation` (HTTP 400) rather than reaching the ORM.

Two operators are rejected at `create()` time for JSON sub-paths, with a
`ValueError` explaining why:

- `contains` -- on a JSON sub-path (a `KeyTransform`) this resolves to
  PostgreSQL's `@>` containment lookup, not substring matching, and raises
  `NotSupportedError` on SQLite. Use `icontains` for substring matching.
- `range` -- expects a two-element sequence, but a filter only ever
  supplies one scalar value from the query string.

`gt`, `gte`, `lt` and `lte` compare numerically, so `create()` requires a
`cast` (e.g. `cast=int`) whenever one of them is listed; omitting it is a
configuration error caught immediately rather than a string comparison
bug found later. Omitting `operators` keeps the default, `exact`-only
matching behaviour, but the query string is not fully inert even then:
`<parameter_name>__op` is always claimed and validated, so submitting one
against a filter created without `operators` (e.g.
`?data__price=10&data__price__op=gte`) now raises `SuspiciousOperation`
(HTTP 400) instead of silently matching zero rows.

The default filter sidebar renders an operator-aware filter as a list of
distinct values, same as any other filter. For a free-text value paired
with the operator dropdown -- the better fit for `gte`/`lte` filters on a
field with too many distinct values to list -- pass
`template='django_utils/admin/lookup_filter.html'`. Any filter built with
`LookupFilterMixin`, not only `JSONFieldFilter`, needs this `template` to
get the operator `<select>` and value input rendered; without it the
operator is still validated, there's just no UI to choose one:

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

`JSONWidgetMixin` works by declaring `formfield_overrides`, so it is a
**silent** no-op in two situations: if `SomeModelAdmin` declares its own
`formfield_overrides` (that dict replaces the mixin's rather than merging
with it), or if the mixin is listed *after* `admin.ModelAdmin` in the
class's bases (`admin.ModelAdmin` already defines an empty
`formfield_overrides`, so MRO finds that one first). Keep the mixin first
in the base list, and merge its `formfield_overrides` mapping into your
own rather than replacing it if you need overrides for other fields too.

## Read-only admin

For operations dashboards, audits, or restricted data access, convert any
`ModelAdmin` to a read-only view — add/change/delete denied for everyone
(superusers included), all fields locked, while list filtering and search
still work. `ReadOnlyModelAdminMixin` is built on stable public `ModelAdmin`
API only:

```python
from django.contrib import admin
from django_utils.admin.mixins import ReadOnlyModelAdminMixin

from myapp.models import MyModel


class ReadOnlyMyModelAdmin(ReadOnlyModelAdminMixin, admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)
    list_filter = ('created_at',)


admin.site.register(MyModel, ReadOnlyMyModelAdmin)
```

The mixin leaves view permission and list configuration untouched, so you
can keep your existing filters, search fields, and display columns. It's a
**silent** no-op if listed *after* `admin.ModelAdmin` (MRO finds
`has_add_permission` on `ModelAdmin` first), so keep the mixin first in the
base list.

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

## Current request / user (ASGI-safe)

Store the current request and user in contextvars for access from anywhere without needing to pass them as function arguments. Unlike thread-local equivalents like `django-crum`, which leak state between interleaved requests under ASGI, `RequestContextMiddleware` uses `contextvars.ContextVar` — isolated per asyncio task and safe under both WSGI and ASGI.

Add the middleware to your Django settings:

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django_utils.context.RequestContextMiddleware',
]
```

Then access the current request or user from model `save()` methods, signal handlers, or any helper code:

```python
from django_utils.context import get_current_request, get_current_user

class MyModel(models.Model):
    def save(self, *args, **kwargs):
        user = get_current_user()
        # `get_current_user()` returns the real `AnonymousUser` instance
        # (which is truthy!) for anonymous requests, so check
        # `is_authenticated`, not just `if user:`.
        if user is not None and user.is_authenticated:
            self.updated_by = user
        super().save(*args, **kwargs)
```

For tests and management commands, use the `current_request()` context manager instead of adding the middleware.

## Query budgets

Catch N+1 regressions in production code paths — not just in tests or behind a development-only debug toolbar.

`django_utils.query_debug.query_budget` counts every query a block executes and logs a warning or raises an exception when the block exceeds its budget. It's production-safe by construction: counting uses Django's `connection.execute_wrapper()` (public API, active regardless of `DEBUG`) instead of accumulating `connection.queries` logs which leak memory in long-lived processes.

Usable as a context manager or a decorator:

```python
from django_utils.query_debug import query_budget

# Warn if a view runs more than 20 queries; fail tests if more than 100
with query_budget(warn_at=20, raise_at=100):
    results = expensive_operation()

# Decorator form: fresh budget per call
@query_budget(warn_at=10)
def my_view(request):
    return render(request, 'template.html', expensive_context())
```

## Auth helpers

Permission checks and decorator helpers for view access control. Django ships
`login_required` and `permission_required`, but `superuser_required` and
`staff_required` must be reimplemented in nearly every project. Likewise,
building permission strings for `user.has_perm()` is always hand-formatted.

```python
from django_utils.auth import superuser_required, staff_required, permission_string

# Decorate views to require superuser (bare or with options)
@superuser_required
def admin_only_view(request):
    return HttpResponse('Admin content')

@superuser_required(raise_exception=True)  # Raises 403 instead of redirecting
def strict_admin_view(request):
    return HttpResponse('Admin content')

# Same for staff
@staff_required
def staff_only_view(request):
    return HttpResponse('Staff content')

# Build permission strings for has_perm checks
if user.has_perm(permission_string(MyModel, 'change')):
    # user can change MyModel instances
    pass
```

## Modern CSRF (Fetch-Metadata) middleware

Modern browsers send request metadata headers that let you reject cross-site state-changing requests before token checks even run — as a second layer, not a replacement. The `Sec-Fetch-Site` header (sent by all modern browsers since ~2019) tells you whether a request is same-origin, same-site, or cross-site — no tokens required.

`FetchMetadataMiddleware` rejects cross-site state-changing requests by header inspection alone, with a fallback to `Origin` header for older browsers. It's **defense-in-depth**: run it *alongside* Django's `CsrfViewMiddleware`, never instead of it. Old browsers and non-browser clients (curl, webhooks) carry neither header and pass through — that's where token CSRF still catches attacks.

The policy, in order:

1. Safe methods (GET/HEAD/OPTIONS/TRACE) always pass.
2. Views marked `@fetch_metadata_exempt` pass.
3. `Sec-Fetch-Site` present: allow `same-origin`/`same-site`/`none` (browser UI); reject everything else with 403 — unknown values fail closed.
4. No `Sec-Fetch-Site`: compare `Origin` header to `scheme://host`; mismatch rejected.
5. Neither header: allow (token CSRF is the backstop).

Behind a TLS-terminating proxy without `SECURE_PROXY_SSL_HEADER` configured, step 4 can false-reject a legacy browser: `request.scheme` reads `http` while its `Origin` header is `https://…`; modern browsers are unaffected since they send `Sec-Fetch-Site`. Configure `SECURE_PROXY_SSL_HEADER` per [the Django docs](https://docs.djangoproject.com/en/stable/ref/settings/#secure-proxy-ssl-header).

Add to `MIDDLEWARE`:

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django_utils.middleware.FetchMetadataMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Keep this
]
```

Exempt specific views with the decorator:

```python
from django_utils.middleware import fetch_metadata_exempt

@fetch_metadata_exempt
def webhook_view(request):
    # This view accepts cross-site requests (e.g., GitHub webhooks)
    return HttpResponse('ok')
```

References: [django/new-features #98](https://github.com/django/new-features/issues/98), [Go's approach](https://pkg.go.dev/net/http#CrossOriginProtection).

## Subquery aggregates

Annotating two one-to-many relations together is a footgun: `annotate(Count('review'), Count('topping'))` implements each aggregate as a JOIN, so the cartesian product multiplies counts — a sandwich with 2 reviews and 3 toppings reports 6 of each. Use `SubqueryCount`, `SubquerySum`, `SubqueryAvg`, `SubqueryMin`, and `SubqueryMax` to run each aggregate in its own independent subquery instead:

```python
from django_utils.aggregates import SubqueryCount, SubquerySum

Sandwich.objects.annotate(
    reviews=SubqueryCount('review'),
    topping_total=SubquerySum('topping', 'price'),
)
```

Passing a relation name resolves it against the annotated model at query-build time — reverse FK, reverse many-to-many, and forward many-to-many relations are all supported. For anything the name form can't express (an inner `filter()`, a top-N slice, a relation reached through another model), pass a queryset explicitly instead — it's resolved as an `OuterRef('pk')`-correlated subquery either way:

```python
from django.db.models import OuterRef
from django_utils.aggregates import SubqueryCount, SubquerySum

Sandwich.objects.annotate(
    reviews=SubqueryCount(Review.objects.filter(sandwich=OuterRef('pk'))),
    topping_total=SubquerySum(
        Topping.objects.filter(sandwich=OuterRef('pk')), 'price'
    ),
)
```

Annotations support `filter()` and `order_by()` like any other. `SubqueryCount` of an empty set is 0; the column aggregates return `None` for an empty set — wrap in `Coalesce()` for a default.

## Bulk upsert

`bulk_update_or_create()` inserts rows and updates the ones whose unique key already exists — in one `INSERT ... ON CONFLICT DO UPDATE` statement per batch, using Django's own `bulk_create(update_conflicts=True)` under the hood. The naive alternative, a loop of `update_or_create()`, costs two queries per row and is racy between the check and the write.

```python
from django_utils.bulk import bulk_update_or_create

bulk_update_or_create(
    [Ingredient(name='salt', stock=5), Ingredient(name='pepper', stock=3)],
    unique_fields=['name'],
    update_fields=['stock'],
    batch_size=1000,
)
```

Arguments are validated before any query runs (`ValueError` on empty or overlapping field lists, unknown fields, mixed model classes). Backend note: PostgreSQL and SQLite use `unique_fields` as the explicit conflict target; MySQL/MariaDB's `ON DUPLICATE KEY UPDATE` fires on *any* unique constraint — identical with one unique constraint on the model, subtly broader with several.

## Chunked management commands

`ChunkedCommand` is a base class for Django management commands that process large querysets in memory-bounded chunks. It composes with `queryset_iterator` to iterate through data in fixed-size batches, logging progress and supporting resumable checkpointing via `--resume-from` and early stopping via `--limit`. Dry-run mode rolls back all changes via an exception-unwound nested transaction, safe for pytest-django's per-test transactions.

Subclass `ChunkedCommand` and implement `get_queryset()` and `handle_instance(instance)`:

```python
from django_utils.management.commands.base_command import ChunkedCommand
from myapp.models import MyModel

class Command(ChunkedCommand):
    chunksize = 1000  # Optional: customize batch size (default 1000)
    log_every = 1000  # Optional: log progress every N rows (default 1000)

    def get_queryset(self):
        return MyModel.objects.all()

    def handle_instance(self, instance):
        instance.some_field = 'updated'
        instance.save()
```

Command-line options:
- `--chunksize N`: Override the class `chunksize` (default 1000)
- `--resume-from PK`: Skip rows with pk ≤ this value (useful for resuming interrupted runs)
- `--limit N`: Stop after processing N rows and log the resume-from hint
- `--dry-run`: Run inside a transaction and roll everything back
- `--log-every N`: Log progress every N rows (default 1000)

## Links

- Documentation: <https://django-utils-2.readthedocs.io/en/latest/>
- Source: <https://github.com/WoLpH/django-utils>
- Bug reports: <https://github.com/WoLpH/django-utils/issues>
- Package homepage: <https://pypi.org/project/django-utils2/>
- My blog: <http://w.wol.ph/>
