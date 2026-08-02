# Changelog

## 4.1.0

### Added

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
  cursor for `QuerySet.iterator()` on PostgreSQL only -- on MySQL,
  Oracle, and SQLite, `iterator()`'s peak memory is set by the driver,
  not by `chunk_size`, since the driver's default cursor can buffer the
  whole result set client-side regardless of how it's read back.
  `queryset_iterator` avoids that by issuing each chunk as its own
  bounded `LIMIT` query rather than one unbounded query (confirmed: 1
  query for `iterator()` vs. N for `queryset_iterator()` at any table
  size), so the driver never receives more than one chunk at a time.
  SQLite has no server-side cursor to bypass in the first place, so it
  cannot demonstrate this effect either way; the benchmark was
  structurally incapable of observing the failure mode the function
  prevents. The wall-clock cost is real and unchanged from before:
  ~1.09x-1.14x on SQLite. (An earlier version called `gc.collect()`
  after every chunk, which raised that ratio to ~1.6x; that call is now
  opt-in via `gc_collect=True`, off by default.) No out-of-memory
  failure has been reproduced in this repository's benchmark -- the
  claim is narrower: bounded driver-side memory by construction on
  backends that buffer, not a demonstrated fix for a specific crash.
  The docstring has been rewritten accordingly.

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
