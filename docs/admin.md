# Admin power-ups

Everything this package adds to `django.contrib.admin`: JSON-aware
list filters with an operator selector, a validating JSON widget, a
read-only admin mixin, sortable related-object count columns, and
dependency-free CSV/JSON export — each covered below with a
screenshot of the real admin, and the JSON widget backed by a live,
in-browser demo of the shipped JavaScript.

(dropdown-filters)=
## Select / dropdown / autocomplete filters

All of the standard admin list filters are available through
`django_utils.admin.filters`: the original filter (`SimpleListFilter`),
a basic select/dropdown filter (`SimpleListFilterDropdown`), and a
select2-based autocompleting dropdown filter (`SimpleListFilterSelect2`).
On PostgreSQL you can additionally filter on JSON fields by path.

```python
class SomeModelAdmin(admin.ModelAdmin):
    list_filter = (
        JSONFieldFilterSelect2.create('some_json_field__some__sub_path'),
    )
```

That filters a JSON field named `some_json_field` and looks for values
shaped like:

```json
{"some": {"sub_path": "some value"}}
```

By default the results for the JSON filters are cached for 10 minutes;
pass `timeout=` to `create()` to change it.

<!-- screenshot: /_static/screenshots/filters-sidebar.png -->

**Try it live** — {doc}`a live, in-browser demo of the dropdown
filter's shipped JavaScript </demos/dropdown-filter>`: a no-JS link
list that becomes a `<select>` once JavaScript swaps it in.

API reference: {py:class}`~django_utils.admin.filters.SimpleListFilterDropdown`,
{py:class}`~django_utils.admin.filters.SimpleListFilterSelect2`, full module at
{doc}`django_utils.admin`.

(operator-filters)=
## Operator filters

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

`create(operators=...)` accepts `exact`, `contains`, `icontains`,
`startswith`, `gt`, `gte`, `lt`, `lte` and `range`; anything outside
that fixed list raises `ValueError` at `create()` time. At request
time, the operator actually submitted in the query string is checked
against *this filter's own* `operators` — the subset passed to
`create()`, default `('exact',)` — not the full list above, so a
generally-valid operator this particular filter never declared still
raises `SuspiciousOperation` (HTTP 400) rather than reaching the ORM.

`gt`, `gte`, `lt` and `lte` compare numerically, so `create()` requires
a `cast` (e.g. `cast=int`) whenever one of them is listed; omitting it
is a configuration error caught immediately rather than a string
comparison bug found later. Omitting `operators` keeps the default,
`exact`-only matching behaviour, but the query string is not fully
inert even then: `<parameter_name>__op` is always claimed and
validated, so submitting one against a filter created without
`operators` (e.g. `?data__price=10&data__price__op=gte`) raises
`SuspiciousOperation` (HTTP 400) instead of silently matching zero
rows.

:::{dropdown} Caveat: two operators are always rejected for JSON sub-paths
`create()` rejects two operators at class-creation time, with a
`ValueError` explaining why, whenever they're requested for a JSON
sub-path (the only thing this factory ever builds):

- `contains` — on a JSON sub-path (a `KeyTransform`) this resolves to
  PostgreSQL's `@>` containment lookup, not substring matching, and
  raises `NotSupportedError` on SQLite. Use `icontains` for substring
  matching instead.
- `range` — expects a two-element sequence, but a filter only ever
  supplies one scalar value from the query string.
:::

The default filter sidebar renders an operator-aware filter as a list
of distinct values, same as any other filter. For a free-text value
paired with the operator dropdown — the better fit for `gte`/`lte`
filters on a field with too many distinct values to list — pass
`template='django_utils/admin/lookup_filter.html'`. Any filter built
with `LookupFilterMixin`, not only `JSONFieldFilter`, needs this
`template` argument to get the operator `<select>` and value input
rendered; without it the operator is still validated, there's just no
UI to choose one:

```python
JSONFieldFilter.create(
    'data__price',
    operators=('gte', 'lte'),
    cast=int,
    template='django_utils/admin/lookup_filter.html',
)
```

<!-- screenshot: /_static/screenshots/operator-filter.png -->

API reference: {py:class}`~django_utils.admin.filters.JSONFieldFilter`,
{py:class}`~django_utils.admin.filters.LookupFilterMixin`.

(json-widget-section)=
## JSON widget

`django_utils.admin.widgets.JSONWidget` is a drop-in replacement for
the admin's default `JSONField` textarea. Django renders a stored
value on one line (`{"b": 2, "a": [1, 2]}`) and only reports a parse
error after a submit round-trip. `JSONWidget` indents and key-sorts
the value, and validates it as you type, via a small, CSP-safe
vanilla-JS asset (no inline handlers, no `eval`) that degrades to a
plain textarea if JavaScript is unavailable.

Django already preserves malformed JSON input across the round-trip
(`forms.JSONField.bound_data()` returns it as `InvalidJSONInput`
instead of discarding it) — `JSONWidget` does not change that
behaviour. What it adds is pretty-printing of well-formed values and
inline validation feedback; it does not touch how malformed input is
stored or redisplayed.

Enable it per `ModelAdmin` with `JSONWidgetMixin`:

```python
from django_utils.admin.widgets import JSONWidgetMixin


class SomeModelAdmin(JSONWidgetMixin, admin.ModelAdmin):
    pass
```

Nothing is patched globally — a project that only uses this package
for the filters above sees no change to its `JSONField` forms.

:::{dropdown} Caveat: MRO ordering
`JSONWidgetMixin` works by declaring `formfield_overrides`, so it is a
**silent** no-op in two situations:

- `SomeModelAdmin` declares its own `formfield_overrides` — that dict
  replaces the mixin's rather than merging with it, so
  `models.JSONField` is no longer mapped to `JSONWidget` and Django's
  default JSON textarea is used instead. No error, no warning.
- The mixin is listed *after* `admin.ModelAdmin` in the class's bases
  (`class SomeModelAdmin(admin.ModelAdmin, JSONWidgetMixin)`).
  `admin.ModelAdmin` already defines an empty `formfield_overrides`,
  so MRO finds that one first.

Keep the mixin first in the base list, and merge its
`formfield_overrides` mapping into your own rather than replacing it
if you need overrides for other fields too.
:::

<!-- screenshot: /_static/screenshots/json-widget.png -->

**Try it live** — {doc}`a live, in-browser demo of the shipped JSON
widget JavaScript </demos/json-widget>`, exercising the same inline
validation described above.

API reference: {py:class}`~django_utils.admin.widgets.JSONWidget`,
{py:class}`~django_utils.admin.widgets.JSONWidgetMixin`.

## Read-only admin

For operations dashboards, audits, or restricted data access, convert
any `ModelAdmin` to a read-only view — add/change/delete denied for
everyone (superusers included), all concrete fields and many-to-many
relations locked as read-only, while list filtering and search still
work. `ReadOnlyModelAdminMixin` is built on stable public `ModelAdmin`
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

The mixin leaves view permission and list configuration untouched, so
you can keep your existing filters, search fields, and display
columns. It also composes with [`ExportMixin`](#admin-export) for read-only
export dashboards: view and download, never edit.

:::{dropdown} Caveat: MRO ordering
It's a **silent** no-op if listed *after* `admin.ModelAdmin` (MRO
finds `has_add_permission` on `ModelAdmin` first), so keep the mixin
first in the base list.

It also governs the *parent* admin's own permissions only: an
editable `inlines` entry on the wrapped admin is **not** made
read-only by this mixin. Django still denies the write — the change
view's POST path is gated on the parent admin's
`has_change_permission`, which this mixin hard-denies, so nothing is
actually editable through it — but the change-form UI still renders
inline widgets as if it were, which can mislead a user into thinking
edits are possible. Apply this mixin to inline admin classes too if
you want their rendered UI to match.
:::

<!-- screenshot: /_static/screenshots/readonly-admin.png -->

API reference: {py:class}`~django_utils.admin.mixins.ReadOnlyModelAdminMixin`.

(count-columns)=
## Count columns

Adding a related-object count to `list_display` is a common ask, but
the naive approach — a `list_display` method calling
`obj.reviews.count()` — is an N+1 query per row, and reaching for
`annotate(Count(...))` at the queryset level reintroduces the JOIN
fan-out footgun documented in [Subquery aggregates](subquery-aggregates)
the moment a second relation joins it. `CountColumnMixin` adds one or
more sortable, fan-out-immune count columns using
[`SubqueryCount`](subquery-aggregates) under the hood:

```python
from django.contrib import admin
from django_utils.admin.mixins import CountColumnMixin

from myapp.models import Sandwich


class SandwichAdmin(CountColumnMixin, admin.ModelAdmin):
    list_display = ('id',)
    count_columns = ('review', 'topping')


admin.site.register(Sandwich, SandwichAdmin)
```

Each entry in `count_columns` is a relation name (reverse FK, reverse
or forward many-to-many) resolved against the model being
administered. For each one, the mixin annotates the changelist
queryset with a `<relation>_count` column (`review_count`,
`topping_count`, ...) and appends it to `list_display` — unless you've
already placed it yourself, in which case your position and your own
method (if you defined one) win. A hand-written method wins the
display slot but doesn't carry `admin_order_field` unless you set it
yourself — the queryset annotation is still there to sort on. Every
generated column is sortable in the changelist header, same as any
other `admin_order_field`-carrying column.

:::{dropdown} Caveat: MRO ordering
Same MRO rule as the read-only mixin above: list `CountColumnMixin`
*before* `admin.ModelAdmin`, otherwise `get_queryset` and
`get_list_display` silently fall through to Django's own versions and
nothing is added.
:::

<!-- screenshot: /_static/screenshots/count-columns.png -->

API reference: {py:class}`~django_utils.admin.mixins.CountColumnMixin`.

(admin-export)=
## Export

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

::::{tab-set}

:::{tab-item} CSV
```text
name,stock
salt,5
pepper,3
'=cmd|'/c calc'!A1,1
```

Exported text values starting with `=`, `+`, `-`, `@`, a tab or a
carriage return are prefixed with a single quote before being
written — the documented OWASP mitigation for CSV/formula injection,
where spreadsheet applications would otherwise execute those cells as
formulas. Numbers and other non-`str` values are left untouched.
:::

:::{tab-item} JSON
```json
[
  {"name": "salt", "stock": 5},
  {"name": "pepper", "stock": 3}
]
```

Streamed as a JSON array, one object per row, with no CSV-style
prefixing needed — non-string values serialize as their native JSON
types.
:::

::::

:::{dropdown} Caveat: encrypted fields export as plaintext
One caveat for models using
[encrypted fields](encrypted-model-fields): exports
read through the ORM, so encrypted values stream into the download as
**plaintext** — encryption at rest does not survive an export,
deliberately.
:::

Hard scope cap, by design: CSV and JSON only, export only — no XLSX,
no import, no resource classes, ever. For anything heavier —
spreadsheets, round-trip import, custom resource classes — reach for
[django-import-export](https://django-import-export.readthedocs.io/);
this mixin exists for the common 90% case without that package's
weight.

<!-- screenshot: /_static/screenshots/export-actions.png -->

API reference: {py:class}`~django_utils.admin.export.ExportMixin`.
