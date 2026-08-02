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

### Fixed

- `to_json` serialises `datetime`, `date`, `Decimal` and `UUID` via
  `DjangoJSONEncoder` instead of raising `TypeError`.

### Changed

- `queryset_iterator` was benchmarked against
  `QuerySet.iterator(chunk_size=...)` (see `benchmarks/queryset_iterator.py`)
  and lost: on SQLite it is ~1.09x-1.14x slower and uses ~1.85x-1.88x the
  peak memory. (An earlier version called `gc.collect()` after every chunk,
  which raised wall-clock time to ~1.6x; that call was removed.) Its
  docstring now documents the benchmark and recommends
  `QuerySet.iterator(chunk_size=...)` for the general case; the function
  itself is unchanged and still has a narrow use (a new query per chunk
  rather than one long-lived cursor, useful when a connection may be reset
  or recycled mid-iteration).

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
