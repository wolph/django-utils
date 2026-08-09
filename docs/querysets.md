# QuerySets & bulk

ORM helpers for the places where naive Django code burns memory or
produces wrong numbers. `queryset_iterator` bounds memory on both the
client and the database while iterating millions of rows.
`Subquery`-based aggregates avoid the JOIN fan-out that silently
multiplies `annotate(Count(...))` results when combined.
`bulk_update_or_create` upserts in one statement per batch instead of
two racy queries per row.

(qs-iterator)=
## queryset_iterator

`queryset_iterator()` iterates a queryset in fixed-size chunks using
keyset pagination (`WHERE <pk_field> > <cursor> LIMIT chunksize`)
instead of a database cursor: each chunk is fetched as its own
independent query rather than as part of one long-lived cursor kept
open for the whole iteration. It was written after
`QuerySet.iterator()` exhausted memory on a very large table, and the
same query shape brings four distinct benefits beyond the client
driver:

1. **Bounded memory on the Python side.** Only `chunksize` model
   instances are ever alive at once. `QuerySet.iterator(chunk_size=...)`
   makes the same promise, but only where the driver streams. MySQL
   with mysqlclient does not: its default cursor materialises the
   *entire* result set client-side in a C buffer `chunk_size` never
   touches. PostgreSQL with Django's default server-side cursors
   streams properly, so `iterator()` is the better choice there.
   SQLite's stdlib driver steps rows lazily too.
2. **Bounded memory on the database server.** Each chunk is an index
   range scan the planner can stop as soon as it has `chunksize` rows,
   instead of materialising and sorting the entire result set
   (`work_mem`/`sort_buffer_size`, spilling to disk when it doesn't
   fit) before returning the first row.
3. **Read-replica distribution.** Each chunk is its own independent
   statement, so a database router or connection pooler can spread the
   N chunk queries across read replicas. A single long-running query
   pins one connection to one server for its whole duration.
4. **Smaller operational blast radius.** A single heavy query is a
   single point of failure: it can exhaust server memory, hit a
   statement timeout, and hold its transaction snapshot open for as
   long as it runs (blocking PostgreSQL vacuum, growing MySQL/InnoDB
   undo history). Short per-chunk queries release their snapshot
   between chunks, and a chunk that fails partway through a run can be
   retried from the last cursor seen via `start_after` instead of
   restarting the whole query.

```python
from django_utils.queryset import queryset_iterator

last_seen = None
for row in queryset_iterator(
    MyModel.objects.all(),
    pk_field='created_at',
    start_after=last_seen,
):
    process(row)
    last_seen = row.created_at
    checkpoint(last_seen)  # survives a restart
```

**Choosing between the two:** prefer `QuerySet.iterator(chunk_size=...)`
on PostgreSQL with server-side cursors enabled (the default). One
query, and the database holds the unfetched rows, not the driver.
Reach for `queryset_iterator` when that guarantee is not available
(MySQL, Oracle, SQLite, or PostgreSQL with server-side cursors
disabled), or whenever a single long-lived cursor is undesirable for
another reason. Iteration can resume on a connection that was reset
or recycled between chunks, which one open cursor cannot.

:::{dropdown} Benchmark data and keyword options
**Benchmark** (`benchmarks/queryset_iterator.py`, SQLite, 20,000 rows,
chunksize=1000): wall clock is close to parity with `QuerySet.iterator()`
(~1.09x-1.14x across runs). An earlier version called `gc.collect()`
after every chunk; that alone added roughly 37-47% to the default-mode
wall-clock time for no measured reduction in Python-level memory, so
`gc_collect` is off by default. None of benefits 2-4 above were
independently benchmarked in this repository. They follow from the
query shape described, not from measurement. The only measured numbers
are the query counts and wall-clock figures here, and the cost is
real: N small queries instead of 1, plus a modest wall-clock overhead.

**`pk_field`**: column to order and paginate by, instead of the
primary key. Must be unique, indexed, totally ordered and non-nullable
so keyset pagination does not skip or repeat rows. A `NULL` value read
from `pk_field` raises `ValueError`, since the cursor cannot resume
from `NULL`. A non-unique value silently truncates: if several rows
tie on the same `pk_field` value, only the ones that land in the
current chunk are yielded and the rest of that tied group is skipped.

**`start_after`**: resume from a previously seen cursor value instead
of starting from the beginning, so a batch job that died partway
through can continue rather than restart.

**`gc_collect`**: call `gc.collect()` after every chunk. Off by
default, see the benchmark above.
:::

API reference: {py:func}`~django_utils.queryset.queryset_iterator`,
full module at {doc}`django_utils`.

(subquery-aggregates)=
## Subquery aggregates

Annotating two one-to-many relations together is a footgun:
`annotate(Count('review'), Count('topping'))` implements each
aggregate as a JOIN, so the cartesian product multiplies counts.

```python
# Wrong: a sandwich with 2 reviews and 3 toppings reports 6 of each.
Sandwich.objects.annotate(
    reviews=Count('review'),
    toppings=Count('topping'),
)
```

Use `SubqueryCount`, `SubquerySum`, `SubqueryAvg`, `SubqueryMin`, and
`SubqueryMax` to run each aggregate in its own independent subquery
instead. The fix for the example above:

```python
from django_utils.aggregates import SubqueryCount

# Correct: each relation counted in its own subquery, no fan-out.
Sandwich.objects.annotate(
    reviews=SubqueryCount('review'),
    toppings=SubqueryCount('topping'),
)
```

Passing a relation name resolves it against the annotated model at
query-build time. Reverse FK, reverse many-to-many, and forward
many-to-many relations are all supported. For anything the name form
cannot express (an inner `filter()`, a top-N slice, a relation
reached through another model), pass a queryset explicitly instead.
Both forms resolve to an `OuterRef('pk')`-correlated subquery:

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

Annotations support `filter()` and `order_by()` like any other.
`SubqueryCount` of an empty set is 0. The column aggregates
(`SubquerySum`, `SubqueryAvg`, `SubqueryMin`, `SubqueryMax`) return
`None` for an empty set, so wrap them in `Coalesce()` for a default.

:::{dropdown} Caveat: MySQL backend support, and a reserved column name
The correlated subquery lives inside a FROM-clause derived table
(`FROM (SELECT ...) _agg`/`_count`). MySQL earlier than 8.0.14 cannot
reference the outer query's columns from within a derived table and
fails loudly with an unknown-column error. Verified on SQLite and
PostgreSQL 16, both in this repo's CI. Expected to work on
MySQL/MariaDB 8.0.14+, but not CI-verified there.

The column aggregates reserve `agg_value` as the inner annotation
alias. A queryset whose model has a real field or annotation named
`agg_value` raises Django's annotation-conflict error.
:::

`CountColumnMixin` in the admin ([Count columns](count-columns))
builds its sortable `list_display` columns on top of `SubqueryCount`
for exactly this reason.

API reference: {py:class}`~django_utils.aggregates.SubqueryCount`,
{py:class}`~django_utils.aggregates.SubquerySum`.

## Bulk upsert

`bulk_update_or_create()` inserts rows and updates the ones whose
unique key already exists, in one `INSERT ... ON CONFLICT DO UPDATE`
statement per batch, using Django's own
`bulk_create(update_conflicts=True)` under the hood. The naive
alternative, a loop of `update_or_create()`, costs two queries per row
and is racy between the check and the write.

```python
from django_utils.bulk import bulk_update_or_create

bulk_update_or_create(
    [Ingredient(name='salt', stock=5), Ingredient(name='pepper', stock=3)],
    unique_fields=['name'],
    update_fields=['stock'],
    batch_size=1000,
)
```

Arguments are validated before any query runs (`ValueError` on empty
or overlapping field lists, unknown fields, mixed model classes).
Field names accept the same spellings `bulk_create` does: field names
(`owner`), foreign-key attnames (`owner_id`), and the `'pk'` alias.

Each batch is committed independently, with no transaction spanning
all batches. That is deliberate: a crash partway through a large run
leaves the earlier batches durable and the operation resumable. Wrap
the call in `django.db.transaction.atomic()` yourself if you need
all-or-nothing semantics instead. Writes always go through the
model's default database (`Model._base_manager`, no `using`
override). Routing to a non-default alias is a known gap.

::::{tab-set}

:::{tab-item} PostgreSQL / SQLite
Uses `ON CONFLICT` with `unique_fields` as the explicit conflict
target. Only rows conflicting on exactly those fields are updated.
:::

:::{tab-item} MySQL / MariaDB
`ON DUPLICATE KEY UPDATE` fires on *any* unique constraint, ignoring
`unique_fields` as a target selector. Identical behaviour to the
PostgreSQL/SQLite case when the model has one unique constraint,
subtly broader when it has several.
:::

::::

:::{dropdown} Caveat: primary keys on Django 4.2
On Django 5.0+ the returned objects have their primary keys populated
(inserted and conflict-updated rows alike), where the backend can
return rows from a bulk insert at all: PostgreSQL and SQLite can,
MariaDB can, vanilla MySQL never can (its Django backend disables
row-returning inserts on every Django version). On Django 4.2,
`bulk_create(update_conflicts=True)` cannot return IDs anywhere
(Django ticket #34698, fixed in 5.0), so every returned object has
`pk=None` even though its row was written.
:::

API reference: {py:func}`~django_utils.bulk.bulk_update_or_create`.
