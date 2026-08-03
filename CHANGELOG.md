# Changelog

## 4.1.0

### Added

- `django_utils.auth`: `superuser_required` / `staff_required` view decorators
  and `permission_string()` — the helpers behind django/new-features #47 and
  #137 (67 combined reactions) that every project hand-rolls. Both decorators
  work bare (`@superuser_required`) and parameterized
  (`@superuser_required(raise_exception=True)`), with redirect or 403 options,
  and work on both sync and async views.
  `permission_string()` builds the `'app_label.action_modelname'` string every
  `user.has_perm()` call needs from a model class.
- `django_utils.query_debug.query_budget`: production-safe query counting via
  `connection.execute_wrapper()` — warn or raise on N+1 regressions in real code
  paths, where `assertNumQueries` (test-only) and profilers (dev-only) cannot
  live. The dominant N+1 package (nplusone) has been unmaintained since 2018.
- `django_utils.middleware.FetchMetadataMiddleware`: opt-in header-based CSRF
  hardening via `Sec-Fetch-Site`/`Origin` (django/new-features #98, 59
  reactions) — strict by default, fails closed on unknown header values,
  allows header-less clients (token CSRF stays the backstop), with
  `fetch_metadata_exempt` decorator for opt-outs. Defense-in-depth: run
  alongside `CsrfViewMiddleware`, never instead of it.
- `django_utils.aggregates`: `SubqueryCount`, `SubquerySum`, `SubqueryAvg`,
  `SubqueryMin`, `SubqueryMax` — aggregate annotations that run as independent
  subqueries, immune to the JOIN fan-out that makes
  `annotate(Count('a'), Count('b'))` silently multiply counts.
- `django_utils.bulk.bulk_update_or_create`: chunked upsert on Django's
  native `bulk_create(update_conflicts=True)` — one
  `INSERT ... ON CONFLICT DO UPDATE` per batch instead of 2N racy queries.
  Existing upsert packages predate the native API and reinvent raw SQL.
  All argument validation happens before any query runs; PostgreSQL and
  SQLite honour `unique_fields` as the conflict target, MySQL/MariaDB
  fire on any unique constraint (documented in the module).
- `django_utils.management.commands.base_command.ChunkedCommand`: management-command
  base that iterates any queryset through `queryset_iterator` with progress
  logging, `--resume-from` checkpointing for resumable runs, `--limit` for
  early stops, and transactional `--dry-run` (scoped to the queryset's
  database alias) that rolls back via exception unwinding (safe inside
  pytest-django's per-test transactions).
- `django_utils.context`: contextvars-native current request/user access
  (`RequestContextMiddleware`, `get_current_request()`, `get_current_user()`,
  `current_request()` context manager). Safe under ASGI where thread-local
  equivalents like django-crum leak state between interleaved requests.
- `Choice` accepts arbitrary keyword metadata, reachable as attributes:
  `Choice('a', 'Active', color='green')` gives `Status.choices['a'].color`.
  Django's `TextChoices` has no equivalent.
- `Choices.as_enum()` returns a real `enum.Enum` built from the choices, so
  application code can use runtime `isinstance` checks and `match` on real
  enum members while model fields keep taking the raw-value class.
- `ChoicesDict.by_key()` exposes the choices keyed by attribute name,
  returning a copy so callers can't mutate the original mapping.
- `ChoicesDict.grouped()` returns choices nested into Django's `<optgroup>`
  structure (`[(group_label, [(value, label), ...]), ...]`), verified
  against a real Django model field and form widget.
- `SlugMixin` now resolves slug collisions with a numeric suffix
  (`my-thing`, `my-thing-2`, ...) instead of silently producing duplicate
  slugs. Override `slugify_max_attempts` to change the retry ceiling.
- `queryset_iterator` gained three keyword-only options, all backwards
  compatible: `pk_field` iterates by any unique, indexed, ordered column
  instead of the primary key (useful when the pk is a random UUID but a
  monotonic `created_at`/`id` column exists); `start_after` resumes from a
  known cursor value so a batch job that died partway through can
  continue instead of restarting; `gc_collect` restores the optional
  per-chunk `gc.collect()` call (off by default -- see below).
- `django_utils.admin.widgets.JSONWidget`: a `JSONField` admin textarea
  that pretty-prints and key-sorts a well-formed value (Django renders it
  on one line) and validates it inline as you type, via a small,
  CSP-safe vanilla-JS static asset (no inline handlers, no `eval`) that
  degrades to a plain `Textarea` without JavaScript. Django already
  preserves malformed input across the round-trip
  (`forms.JSONField.bound_data()` returns `InvalidJSONInput`); the widget
  does not change that.
- `django_utils.admin.widgets.JSONWidgetMixin`: opts a `ModelAdmin` into
  `JSONWidget` for its `JSONField`s via `formfield_overrides`. Nothing is
  patched globally -- a project using only the filters below sees no
  change to its forms.
- `django_utils.admin.filters.LookupFilterMixin`: adds an operator
  selector to a list filter. The operator is read from
  `<parameter_name>__op` and validated at request time against the
  filter's own `operators` (default `('exact',)`) before use, raising
  `SuspiciousOperation` for anything not in that set. A custom filter
  that mixes this in must also point `template` at
  `django_utils/admin/lookup_filter.html` to render the operator
  `<select>` and value input -- without it the operator is still
  enforced, just with no UI to choose one.
- `JSONFieldFilter.create()` gained an `operators` keyword to enable the
  above on JSON sub-path filters, e.g.
  `create('data__price', operators=('gte',), cast=int)`. The keyword
  itself is validated against a fixed allowlist (`exact`, `contains`,
  `icontains`, `startswith`, `gt`, `gte`, `lt`, `lte`, `range`) at
  `create()` time -- this is `JSONFieldFilter.create()`'s own check, not
  the request-time one described above. `contains` and `range` are
  further rejected at `create()` time for JSON sub-paths: `contains` on
  a `KeyTransform` resolves to PostgreSQL's `@>` containment lookup, not
  substring matching, and raises `NotSupportedError` on SQLite (use
  `icontains`); `range` expects a two-element sequence but a filter only
  ever supplies one scalar. Omitting `operators` keeps the default,
  `exact`-only matching behaviour, but the query string is not fully
  inert even then: `<parameter_name>__op` is now always claimed and
  validated, so e.g. `?data__price=10&data__price__op=gte` against a
  filter created without `operators` now raises `SuspiciousOperation`
  (HTTP 400) instead of the previous silent zero-row match.
- `django_utils.views.error_400`: completes the shipped error-handler set
  (403/404/500 already existed), so a project's `handler400` can point
  here too. Renders `django_utils/error_400.html`, which shipped in
  every release but had no view referencing it.
- Test infrastructure: template coverage. `django-coverage-plugin` now
  measures the shipped `.html` templates as part of the combined 100%
  coverage gate, so an unrendered template line fails CI instead of
  being invisible to coverage.py. Enabling it immediately surfaced --
  and forced render tests for -- `dropdown_filter.html` and
  `select2_filter.html`, which no test had ever rendered.

### Fixed

- `to_json` serialises `datetime`, `date`, `Decimal` and `UUID` via
  `DjangoJSONEncoder` instead of raising `TypeError`.

### Changed

- A prior version of this changelog reported that `queryset_iterator`
  was benchmarked against `QuerySet.iterator(chunk_size=...)` and lost.
  That conclusion was wrong and has been corrected. The benchmark
  (`benchmarks/queryset_iterator.py`) ran on SQLite and measured
  `tracemalloc` peak, which tracks Python-level allocations only; it
  cannot see a database driver's C-level result buffer, which is exactly
  what `queryset_iterator` exists to bound. Django opens a server-side
  cursor for `QuerySet.iterator()` on PostgreSQL only. Off that path,
  `iterator()`'s peak memory is set by the driver, not by `chunk_size`,
  on backends whose driver buffers the whole result set client-side --
  verified for MySQL with mysqlclient (its default cursor calls
  `store_result()`); driver-dependent, and not established here, for
  Oracle and for PostgreSQL with `DISABLE_SERVER_SIDE_CURSORS = True`.
  `queryset_iterator` avoids that by issuing each chunk as its own
  bounded `LIMIT` query rather than one unbounded query (confirmed: 1
  query for `iterator()` vs. N for `queryset_iterator()` at any table
  size), so the driver never receives more than one chunk at a time.
  SQLite has no server-side cursor to bypass in the first place, but its
  stdlib driver steps rows lazily rather than buffering the whole result
  set, so it cannot demonstrate this effect either way; the benchmark
  was structurally incapable of observing the failure mode the function
  prevents. The wall-clock cost is real and unchanged from before:
  ~1.09x-1.14x on SQLite. (An earlier version called `gc.collect()`
  after every chunk, which raised that ratio to ~1.6x; that call is now
  opt-in via `gc_collect=True`, off by default.) No out-of-memory
  failure has been reproduced in this repository's benchmark -- the
  claim is narrower: bounded driver-side memory by construction on
  backends that buffer, not a demonstrated fix for a specific crash.
  The docstring has been rewritten accordingly.
- `queryset_iterator`'s docstring now documents why the chunked query
  shape helps beyond client-side driver memory: bounded memory on the
  database server (each chunk is an indexed range scan the planner can
  satisfy incrementally, instead of one query that may force the
  server to materialise and sort the full result set) and
  distribution across read replicas (N independent statements can be
  load-balanced; one long-running query cannot). It also covers the
  operational blast radius of a single heavy query and how short,
  resumable chunks (`start_after`) avoid it. These three points follow
  from the query shape and were not independently benchmarked.

## 4.0.0 (unreleased)

Modernization release. Runtime behavior of retained APIs is unchanged except for the documented fixes below; the removed modules were packaging/metadata only.

### Breaking

- Dropped support for Python < 3.10 and Django < 4.2.
  Supported: Python 3.10-3.14, Django 4.2 / 5.2 / 6.0.
- Removed `django_utils.__about__`; package metadata now lives in
  `pyproject.toml` (use `importlib.metadata.version('django-utils2')`).
- Removed the empty `django_utils/models.py` module.
- Django is now an explicit install dependency (`django>=4.2`); 3.x
  releases only declared `python-utils`.
- A JSONP `callback` parameter must now be a valid Python identifier.
  Deployments relying on dotted or subscripted callback names such as
  `angular.callbacks._0`, `window.cb`, or `cb[0]` will now get a 400
  response instead.
- `RecursiveField` no longer inherits the parent's value when the
  child's own value is falsy (`0`, `''`, `False`); previously such
  values were treated as unset. Code relying on the parent value
  being substituted for a falsy child will now see the child's value
  instead.

### Fixed

- `FilterBase.create(formatter=..., cast=...)`: user-supplied callables
  were bound as methods and crashed when invoked with the documented
  single argument. They are now wrapped in `staticmethod`.
- Filter lookup caching: `timeout=timedelta(0)` now disables caching
  instead of silently using the 10-minute default.
- `ChoicesMeta` no longer accumulates attributes from every
  `LiteralChoices` subclass defined in the process.
- Admin filters module is now fully covered by tests (it previously had
  none and was excluded from coverage).
- The `settings` management command no longer reports the deprecated
  `USE_L10N` setting on Django 4.2.
- The `?debug=1` view of an ajax response is now restricted to
  `settings.DEBUG` or clients in `settings.INTERNAL_IPS`, and its output is
  HTML-escaped. A JSONP `callback` parameter must now be a valid Python
  identifier.
- The `debug` template filter returns an empty string unless
  `settings.DEBUG` is enabled, matching Django's own `{% debug %}` tag, and
  no longer renders protected attributes.
- Admin filter lookups now honour the `ModelAdmin`'s per-request queryset
  instead of querying the model's default manager, and cached lookups are
  scoped per user. Override `get_lookups_cache_scope()` to share the cache
  between users.
- `queryset_iterator` no longer skips rows whose primary key is zero or
  negative; a queryset whose primary keys were all negative previously
  yielded nothing.
- `RecursiveField` no longer treats a falsy child value (`0`, `''`,
  `False`) as unset and inherits the parent's value in its place.
- `Choices` subclasses may declare `_ignore_` to keep constants from being
  collected as choices.

### Changed

- Packaging: `pyproject.toml` with the `uv_build` backend; added a
  proper BSD-3-Clause `LICENSE` file and a `py.typed` marker (the whole
  package is strictly typed and checked by mypy, basedpyright, pyrefly
  and ty). Views decorated with `env` can now be typed against the new
  `django_utils.view_decorators.EnvRequest` request class.
- Linting/formatting: ruff (replaces flake8).
- CI: split into ci/codeql/publish workflows; releases publish to PyPI
  via Trusted Publishing on `v*` tags.
- Docs: furo theme, README converted to Markdown.
- Filter lookup cache keys are now hashed (`django_utils.lookups.<sha256>`)
  so they are valid on every cache backend; previously the raw request
  path and filter title were concatenated, producing keys with spaces
  that memcached rejects. Cached lookups are invalidated once on upgrade.

## 3.0.2 and earlier

See the git history.
