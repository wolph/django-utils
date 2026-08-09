# Admin power-ups

Everything this package adds to `django.contrib.admin`: JSON-aware
list filters with an operator selector, a validating JSON widget, a
read-only admin mixin, sortable related-object count columns, and
dependency-free CSV/JSON export. Each section shows the real admin in
a screenshot, and the filters and the JSON widget both have live
in-browser demos of the shipped JavaScript.

(dropdown-filters)=
## Select / dropdown / autocomplete filters

All of the standard admin list filters are available through
`django_utils.admin.filters`: the original filter (`SimpleListFilter`),
a basic select/dropdown filter (`SimpleListFilterDropdown`), and a
select2-based autocompleting dropdown filter (`SimpleListFilterSelect2`).
You can additionally filter on JSON fields by path on any backend.
The one PostgreSQL-specific operator, `contains`, is rejected by
`create()` with a pointer at `icontains`.

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

By default the results for the JSON filters are cached for 10
minutes. Pass `timeout=` to `create()` to change it.

:::{figure} /_static/screenshots/filters-sidebar.png
:alt: Django admin changelist for Sandwich with the "By Data Filling" JSON dropdown filter open in the sidebar, listing All, Avocado, Bacon, Cheddar, Corned Beef and Turkey.
:width: 700px

The `data__filling` dropdown filter, open in the sidebar. Five seeded
filling values (more than three) is what makes `dropdown_filter.js`
swap the no-JS link list for this `<select>`.
:::

**Try it live**: {doc}`the dropdown filter demo </demos/dropdown-filter>`
runs the shipped JavaScript in your browser, from the no-JS link list
to the select2 autocomplete.

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
`startswith`, `gt`, `gte`, `lt`, `lte` and `range`. Anything outside
that fixed list raises `ValueError` at `create()` time. At request
time, the submitted operator is checked against *this filter's own*
`operators`, the subset passed to `create()` (default `('exact',)`),
not the full list above. A generally valid operator this particular
filter never declared raises `SuspiciousOperation` (HTTP 400) before
it can reach the ORM.

`gt`, `gte`, `lt` and `lte` compare numerically, so `create()`
requires a `cast` (for example `cast=int`) whenever one of them is
listed. Omitting the cast would be a string comparison bug found
later, so it is a configuration error caught immediately instead.
Omitting `operators` keeps the default `exact`-only matching, but the
query string is not fully inert even then: `<parameter_name>__op` is
always claimed and validated, so submitting
`?data__price=10&data__price__op=gte` against a filter created
without `operators` raises `SuspiciousOperation` instead of silently
matching zero rows.

:::{dropdown} Caveat: two operators are always rejected for JSON sub-paths
`create()` rejects two operators at class-creation time, with a
`ValueError` explaining why, whenever they're requested for a JSON
sub-path (the only thing this factory ever builds):

- `contains`: on a JSON sub-path (a `KeyTransform`) this resolves to
  PostgreSQL's `@>` containment lookup, not substring matching, and
  raises `NotSupportedError` on SQLite. Use `icontains` for substring
  matching instead.
- `range`: expects a two-element sequence, but a filter only ever
  supplies one scalar value from the query string.
:::

The default filter sidebar renders an operator-aware filter as a list
of distinct values, same as any other filter. For a free-text value
paired with the operator dropdown, the better fit for `gte`/`lte` on
a field with too many distinct values to list, pass
`template='django_utils/admin/lookup_filter.html'`. Any filter built
with `LookupFilterMixin`, not only `JSONFieldFilter`, needs this
`template` argument to render the operator `<select>` and value
input. Without it the operator is still validated, there is just no
UI to choose one:

```python
JSONFieldFilter.create(
    'data__price',
    operators=('gte', 'lte'),
    cast=int,
    template='django_utils/admin/lookup_filter.html',
)
```

:::{figure} /_static/screenshots/operator-filter.png
:alt: Django admin changelist for Sandwich with the "By Data Price" operator filter showing a "gte" operator select and a value input filled in with 550, filtering the list to four rows.
:width: 700px

The `data__price` operator filter, submitted with `gte` and `550`.
Both the operator `<select>` and the value `<input>` are populated
straight from the query string, and the changelist below is filtered
accordingly.
:::

API reference: {py:class}`~django_utils.admin.filters.JSONFieldFilter`,
{py:class}`~django_utils.admin.filters.LookupFilterMixin`.

(json-widget-section)=
## JSON widget

`django_utils.admin.widgets.JSONWidget` is a drop-in replacement for
the admin's default `JSONField` textarea. Django renders a stored
value on one line (`{"b": 2, "a": [1, 2]}`) and only reports a parse
error after a submit round-trip. `JSONWidget` indents and key-sorts
the value, validates it as you type, and syntax-highlights keys,
strings, numbers and literals while you edit. The highlighting is a
colored overlay on a still fully native `<textarea>`, follows the
admin's light and dark themes, and needs no highlighting library. The
whole widget is a small, CSP-safe vanilla-JS asset with no inline
handlers and no `eval`, and it degrades to a plain textarea if
JavaScript is unavailable.

Django already preserves malformed JSON input across the round-trip:
`forms.JSONField.bound_data()` returns it as `InvalidJSONInput`
instead of discarding it. `JSONWidget` does not change that
behaviour. It only adds pretty-printing, validation feedback and
highlighting on top.

Enable it per `ModelAdmin` with `JSONWidgetMixin`:

```python
from django_utils.admin.widgets import JSONWidgetMixin


class SomeModelAdmin(JSONWidgetMixin, admin.ModelAdmin):
    pass
```

Nothing is patched globally. A project that only uses this package
for the filters above sees no change to its `JSONField` forms.

:::{dropdown} Caveat: MRO ordering
`JSONWidgetMixin` works by declaring `formfield_overrides`, so it is a
**silent** no-op in two situations:

- `SomeModelAdmin` declares its own `formfield_overrides`: that dict
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

:::{figure} /_static/screenshots/json-widget.png
:alt: Django admin change form for a Sandwich with a JSONWidget textarea containing a multi-key JSON document with a missing closing brace, and a red inline error reading "Expected ',' or '}' after property value in JSON".
:width: 700px

`JSONWidget` on a change form: a pretty-printed, multi-key document,
broken here (missing closing brace) to show the inline validation
error `json_widget.js` adds. The message is the browser's own
`JSON.parse()` error, reported as you type.
:::

**Try it live**: {doc}`the JSON widget demo </demos/json-widget>`
runs the same shipped JavaScript in your browser, validation and
syntax highlighting included.

API reference: {py:class}`~django_utils.admin.widgets.JSONWidget`,
{py:class}`~django_utils.admin.widgets.JSONWidgetMixin`.

## Read-only admin

For operations dashboards, audits, or restricted data access, convert
any `ModelAdmin` to a read-only view. Add, change and delete are
denied for everyone, superusers included. All concrete fields and
many-to-many relations render read-only, while list filtering and
search keep working. `ReadOnlyModelAdminMixin` is built on stable
public `ModelAdmin` API only:

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
read-only by this mixin. Django still denies the write, because the
change view's POST path is gated on the parent admin's
`has_change_permission`, which this mixin hard-denies. But the
change-form UI still renders inline widgets as if edits were
possible, which can mislead a user. Apply this mixin to inline admin
classes too if you want their rendered UI to match.
:::

:::{figure} /_static/screenshots/readonly-admin.png
:alt: Django admin "View tag" screen for a Tag showing ID, Name and Sandwiches as read-only rows, with only a Close button and no Save or Delete.
:width: 700px

A `ReadOnlyModelAdminMixin`-wrapped `Tag` change view: `name` and the
`sandwiches` many-to-many both render read-only, the page title reads
"View tag" rather than "Change tag", and only Close remains. No Save,
no Delete.
:::

API reference: {py:class}`~django_utils.admin.mixins.ReadOnlyModelAdminMixin`.

(count-columns)=
## Count columns

Adding a related-object count to `list_display` is a common ask, but
both obvious routes have a cost. A `list_display` method calling
`obj.reviews.count()` is an N+1 query per row. Reaching for
`annotate(Count(...))` at the queryset level reintroduces the JOIN
fan-out documented in [Subquery aggregates](subquery-aggregates) the
moment a second relation joins it. `CountColumnMixin` adds sortable,
fan-out-immune count columns using
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
`topping_count`, and so on) and appends it to `list_display`. If you
already placed the column yourself, your position and your own method
win. A hand-written method keeps the display slot but does not carry
`admin_order_field` unless you set it yourself. The queryset
annotation is still there to sort on, and every generated column
sorts in the changelist header like any other
`admin_order_field`-carrying column.

:::{dropdown} Caveat: MRO ordering
Same MRO rule as the read-only mixin above: list `CountColumnMixin`
*before* `admin.ModelAdmin`, otherwise `get_queryset` and
`get_list_display` silently fall through to Django's own versions and
nothing is added.
:::

:::{figure} /_static/screenshots/count-columns.png
:alt: Django admin changelist for Sandwich with Review count and Topping count columns, sorted descending by Review count (3, 2, 1, 0, 0).
:width: 700px

`CountColumnMixin`'s `review_count` / `topping_count` columns on the
Sandwich changelist, sorted descending by review count. Both sort
exactly like any other `admin_order_field`-carrying column.
:::

API reference: {py:class}`~django_utils.admin.mixins.CountColumnMixin`.

(admin-export)=
## Export

`ExportMixin` adds two changelist actions, `export_as_csv` and
`export_as_json`, that stream the selected rows straight to the
client via `StreamingHttpResponse`. Rows are pulled one at a time
through `queryset_iterator`, so exporting a million rows never loads
the whole table into memory:

```python
from django.contrib import admin
from django_utils.admin.export import ExportMixin

from myapp.models import Ingredient


class IngredientAdmin(ExportMixin, admin.ModelAdmin):
    list_display = ('name', 'stock')
    export_fields = ('name', 'stock')  # Optional. Defaults to every
                                        # concrete field's attname.


admin.site.register(Ingredient, IngredientAdmin)
```

Both actions run against the changelist's own queryset, already
narrowed by `list_filter`, search, and this package's own admin
filters. The intended flow is filter first, select second, export
third. The export never sees a row the changelist would not have
shown.

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
written. That is the documented OWASP mitigation for CSV formula
injection, where spreadsheet applications would otherwise execute
those cells as formulas. Numbers and other non-`str` values are left
untouched.
:::

:::{tab-item} JSON
```json
[
  {"name": "salt", "stock": 5},
  {"name": "pepper", "stock": 3}
]
```

Streamed as a JSON array, one object per row, with no CSV-style
prefixing needed. Non-string values serialize as their native JSON
types.
:::

::::

:::{dropdown} Caveat: encrypted fields export as plaintext
One caveat for models using
[encrypted fields](encrypted-model-fields): exports
read through the ORM, so encrypted values stream into the download as
**plaintext**. Encryption at rest does not survive an export,
deliberately.
:::

The scope is capped by design: CSV and JSON, export only. No XLSX, no
import, no resource classes. For anything heavier, reach for
[django-import-export](https://django-import-export.readthedocs.io/).
This mixin exists for the common case without that package's weight.

:::{figure} /_static/screenshots/export-actions.png
:alt: Django admin changelist for Ingredient with all four rows selected and the action selector expanded, listing Delete selected ingredients, Export selected as CSV and Export selected as JSON.
:width: 700px

The changelist action selector, expanded, showing both `ExportMixin`
actions alongside Django's own built-in delete action.
:::

API reference: {py:class}`~django_utils.admin.export.ExportMixin`.
