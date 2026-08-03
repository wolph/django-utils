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
(superusers included), all concrete fields and many-to-many relations locked
as read-only, while list filtering and search still work.
`ReadOnlyModelAdminMixin` is built on stable public `ModelAdmin` API only:

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
base list. It also composes with
[`ExportMixin`](#admin-export) for read-only export dashboards: view and
download, never edit.

## Count columns in the admin

Adding a related-object count to `list_display` is a common ask, but the
naive approach — a `list_display` method calling `obj.reviews.count()` — is
an N+1 query per row, and reaching for `annotate(Count(...))` at the
queryset level reintroduces the JOIN fan-out footgun documented above the
moment a second relation joins it. `CountColumnMixin` adds one or more
sortable, fan-out-immune count columns using
[`SubqueryCount`](#subquery-aggregates) under the hood:

```python
from django.contrib import admin
from django_utils.admin.mixins import CountColumnMixin

from myapp.models import Sandwich


class SandwichAdmin(CountColumnMixin, admin.ModelAdmin):
    list_display = ('id',)
    count_columns = ('review', 'topping')


admin.site.register(Sandwich, SandwichAdmin)
```

Each entry in `count_columns` is a relation name (reverse FK, reverse or
forward many-to-many) resolved against the model being administered. For
each one, the mixin annotates the changelist queryset with a
`<relation>_count` column (`review_count`, `topping_count`, ...) and
appends it to `list_display` — unless you've already placed it yourself,
in which case your position and your own method (if you defined one) win.
(A hand-written method wins the display slot but doesn't carry
`admin_order_field` unless you set it yourself — the queryset annotation
is still there to sort on.) Every generated column is sortable in the
changelist header, same as any other `admin_order_field`-carrying column.

Same MRO rule as the read-only mixin above: list `CountColumnMixin`
*before* `admin.ModelAdmin`, otherwise `get_queryset` and
`get_list_display` silently fall through to Django's own versions and
nothing is added.

## Admin export

`ExportMixin` adds two changelist actions — `export_as_csv` and
`export_as_json` — that stream the selected rows straight to the
client via `StreamingHttpResponse`, pulling rows one at a time through
`queryset_iterator` so exporting a million rows never loads the whole
table into memory:

```python
from django.contrib import admin
from django_utils.admin.export import ExportMixin

from myapp.models import Ingredient


class IngredientAdmin(ExportMixin, admin.ModelAdmin):
    list_display = ('name', 'stock')
    export_fields = ('name', 'stock')  # optional; defaults to every
                                        # concrete field's attname


admin.site.register(Ingredient, IngredientAdmin)
```

Both actions run against the *changelist's own queryset* — already
narrowed by `list_filter`, search, and this package's own admin
filters (`django_utils.admin.filters`) — so the intended flow is
filter first, select second, export third: the export never sees a
row the changelist wouldn't have shown.

Exported CSV text values starting with `=`, `+`, `-`, `@`, a tab or a
carriage return are prefixed with a single quote before being written —
the documented OWASP mitigation for CSV/formula injection, where
spreadsheet applications would otherwise execute those cells as
formulas. Numbers and other non-str values are left untouched.

One caveat for models using
[encrypted fields](#encrypted-model-fields): exports read through the
ORM, so encrypted values stream into the download as **plaintext** —
encryption at rest does not survive an export, deliberately.

Hard scope cap, by design: CSV and JSON only, export only — no XLSX,
no import, no resource classes, ever. For anything heavier —
spreadsheets, round-trip import, custom resource classes — reach for
[django-import-export](https://django-import-export.readthedocs.io/);
this mixin exists for the common 90% case without that package's
weight.

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

## PostgreSQL ENUM field

`django_utils.pg_enum.EnumField` wires a `Choices` class straight to a
`CharField`: `choices` and `max_length` are derived from it, and on
PostgreSQL the column's real type is a native `CREATE TYPE ... AS ENUM`
type instead of `VARCHAR` -- the database itself then rejects a row that
doesn't hold one of the declared values, on top of (not instead of)
Django's own choice validation. On every other backend `db_type()` falls
back to plain `VARCHAR`, so a model using `EnumField` stays portable --
SQLite never sees a Postgres-specific type name:

```python
from django.db import models
from django_utils import choices, pg_enum


class OrderStatus(choices.Choices):
    Pending = choices.Choice('pending', 'Pending')
    Shipped = choices.Choice('shipped', 'Shipped')
    Delivered = choices.Choice('delivered', 'Delivered')


class Order(models.Model):
    status = pg_enum.EnumField(OrderStatus, default=OrderStatus.Pending)
```

`enum_type` defaults to the `Choices` class name in snake_case
(`OrderStatus` -> `'order_status'`); pass it explicitly to use a
different PostgreSQL type name.

### Hand-written migration operations

The field never issues DDL for the enum type itself -- Django's
`makemigrations` autodetector has no concept of "create this standalone
database object first". Add explicit operations to a migration BY HAND
instead. `CreateEnumType` must run before the operation that adds a column
using it, so it belongs in the same migration, ahead of `AddField`:

```python
import myapp.models
from django.db import migrations
from django_utils import pg_enum


class Migration(migrations.Migration):
    dependencies = [...]

    operations = [
        pg_enum.CreateEnumType(
            'order_status', ['pending', 'shipped', 'delivered']
        ),
        migrations.AddField(
            model_name='order',
            name='status',
            field=pg_enum.EnumField(myapp.models.OrderStatus, default='pending'),
        ),
    ]
```

Both are DB-only (no model-state changes) and no-ops on every
non-PostgreSQL vendor, so a migration using them still applies cleanly
against SQLite or MySQL -- just without the enum type's extra
database-level integrity check. `CreateEnumType` reverses to `DROP TYPE`;
`DropEnumType` is the inverse (it takes the same `values` so *its*
reversal has something to recreate).

#### `AddEnumValue` needs its own migration, with `atomic = False` on the class

`AddEnumValue` sets `atomic = False` on itself, but **that alone is not
enough**. Django's migration executor opens its schema editor -- and with
it, the wrapping transaction -- keyed on the **Migration's** `atomic`
attribute (default `True`), *before* any operation's own `atomic` flag is
ever consulted; an operation-level flag can only add extra wrapping inside
an already-open transaction, never escape one that's already open. This is
the same reason Django's own `AddIndexConcurrently` requires
`atomic = False` on the Migration class, not just the operation. Skip it
and `AddEnumValue.database_forwards` raises `NotSupportedError` instead of
running somewhere it can't safely run:

```python
class Migration(migrations.Migration):
    dependencies = [...]
    atomic = False  # required -- see above; the operation's own
    # atomic = False cannot escape this Migration's transaction on its own.

    operations = [
        pg_enum.AddEnumValue('order_status', 'cancelled'),
    ]
```

`AddEnumValue` is also irreversible -- PostgreSQL has no `DROP VALUE` at
all, on any version. If you need to remove a value, recreate the type
instead:

```python
class Migration(migrations.Migration):
    dependencies = [...]

    operations = [
        pg_enum.CreateEnumType(
            'order_status_v2', ['pending', 'shipped', 'delivered']
        ),
        migrations.AlterField(
            model_name='order',
            name='status',
            field=pg_enum.EnumField(
                myapp.models.OrderStatus, enum_type='order_status_v2'
            ),
        ),
        migrations.RunSQL(
            "ALTER TABLE myapp_order ALTER COLUMN status TYPE "
            "order_status_v2 USING status::text::order_status_v2",
            reverse_sql=migrations.RunSQL.noop,
        ),
        pg_enum.DropEnumType(
            'order_status', ['pending', 'shipped', 'delivered', 'cancelled']
        ),
    ]
```

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

## Encrypted model fields

`EncryptedCharField`, `EncryptedTextField` and `EncryptedJSONField` store a
Fernet-encrypted token in a plain `TEXT` column -- encryption at rest for
values you never need to query, sort or index by (an API key, a bank
account number, free-text notes). All crypto goes through
[`cryptography`](https://cryptography.io/)'s `Fernet`/`MultiFernet` --
nothing hand-rolled, no `hazmat` primitives touched directly. Requires the
`crypto` extra: `pip install "django-utils2[crypto]"`. Importing
`django_utils.crypto_fields` works without `cryptography` installed;
*instantiating* any of the three fields without it raises
`ImproperlyConfigured` naming that install command -- and since fields
instantiate as part of executing a model's class body, a model that
*declares* one of them fails at app-import/`django.setup()` time, not on
first use: the whole app fails to boot, loudly and immediately, if the
extra is missing.

```python
from django.db import models
from django_utils.crypto_fields import (
    EncryptedCharField,
    EncryptedJSONField,
    EncryptedTextField,
)


class Customer(models.Model):
    tax_id = EncryptedCharField(max_length=20)
    notes = EncryptedTextField(blank=True)
    payment_details = EncryptedJSONField(null=True, blank=True)
```

Keys live in `settings.DJANGO_UTILS_FERNET_KEYS`, a list of urlsafe-base64
32-byte keys (`Fernet.generate_key()`):

```python
DJANGO_UTILS_FERNET_KEYS = [
    'the-current-key...',
    'the-previous-key...',  # still needed to decrypt old rows
]
```

**Rotation story:** the FIRST key encrypts; EVERY key is tried on decrypt.
Rotate by prepending a new key and redeploying -- existing rows keep
decrypting fine under the old key (now second in the list), and get
re-encrypted under the new (first) key the next time each row is saved.
There is no bulk re-encryption command here; touch (`.save()`) the rows
you want migrated on your own schedule, e.g. with
[`ChunkedCommand`](#chunked-management-commands). Once every row has been
resaved, drop the old key from the list -- rows that were never resaved
under it become undecryptable (`ValidationError` on read) the moment it's
removed.

**Non-goals, loudly:**
- No queryable or searchable encryption. Fernet salts every encryption,
  so two rows with identical plaintext get different ciphertext -- even
  `exact` can never match at the database level. Every lookup except
  `isnull` raises `NotImplementedError`; filter in Python after decrypting,
  or maintain a separate searchable hash column alongside the encrypted
  one. This includes this package's own admin features: a
  [`JSONFieldFilter`](#admin-select--dropdown--autocomplete-json-filters)
  or `search_fields` entry pointing at an encrypted field makes the
  changelist raise that same `NotImplementedError` at request time -- a
  configuration error surfaced loudly, not a silent empty result.
- Ordering is not blocked (Django offers no field-level hook for it),
  but `order_by()` on an encrypted field sorts by ciphertext -- a
  meaningless order. Don't.
- Encryption at rest only: anything that reads through the ORM sees
  plaintext -- including this package's own
  [`ExportMixin`](#admin-export) (an export action on an encrypted model
  streams decrypted values into the CSV/JSON download) and Django's
  `dumpdata` (fixtures land on disk in plaintext).
- No per-field keys. One keyring (`DJANGO_UTILS_FERNET_KEYS`) for every
  encrypted field in the project.
- No deterministic mode. If you need same-plaintext-same-ciphertext,
  this is the wrong tool -- it also reintroduces exactly the equality
  side-channel Fernet's salting exists to prevent.

`EncryptedCharField`'s `max_length` validates the PLAINTEXT (a
`MaxLengthValidator`, same as plain `CharField`); it never sizes the
column, which always stores the necessarily-longer ciphertext instead.
`from_db_value` decrypts eagerly, as each row is fetched -- a token
nothing in `DJANGO_UTILS_FERNET_KEYS` can decrypt raises `ValidationError`
out of the fetch itself (`.get()`, `.refresh_from_db()`, iterating a
queryset), not lazily on later attribute access.

## Links

- Documentation: <https://django-utils-2.readthedocs.io/en/latest/>
- Source: <https://github.com/WoLpH/django-utils>
- Bug reports: <https://github.com/WoLpH/django-utils/issues>
- Package homepage: <https://pypi.org/project/django-utils2/>
- My blog: <http://w.wol.ph/>
