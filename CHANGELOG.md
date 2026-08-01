# Changelog

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
