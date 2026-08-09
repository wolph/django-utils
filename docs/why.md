# Why django-utils2

django-utils2 grew where an existing package stopped maintaining its
answer, or never had one. This page names those packages, states what
this library does differently, and lists the quality gates every
release has to pass. Every claim is backed by this repository itself:
the README, the CHANGELOG, or the CI configuration that enforces it.

## How it compares

**django-crum** stores the current request and user in a thread-local.
Under ASGI, one thread's event loop interleaves many concurrent
requests as asyncio tasks, so a thread-local leaks state between them.
`django_utils.context.RequestContextMiddleware` uses
`contextvars.ContextVar` instead, which is isolated per asyncio task
and therefore correct under both WSGI and ASGI. See
[Current request / user (ASGI-safe)](current-request-user).

**nplusone** is the dominant N+1-detection package for Django and has
not shipped a release since 2018. `django_utils.query_debug.query_budget`
counts queries through Django's own `connection.execute_wrapper()`,
which works with `DEBUG` off and in real request paths, not only in
tests or a dev-only debug toolbar. See [Query budgets](query-budgets).

## Quality gates

- **CSP-safe markup everywhere.** The JSON widget and the
  dropdown/select2 admin filters ship as small vanilla-JS assets with
  no inline handlers, no inline `<script>`, and no inline `style=`.
  This guarantee had to be earned: before 4.1.0 the filter templates
  emitted all three. A dedicated test (`tests/test_docs_demos.py`)
  enforces the same rule on the docs site's live demo pages.
- **100% test coverage, including templates.** `django-coverage-plugin`
  measures the shipped `.html` templates inside the same
  `coverage report --fail-under=100` gate as the Python code, so an
  unrendered template line fails CI instead of staying invisible.
- **Six type checkers and linters on every CI run:** `ruff check`,
  `ruff format --check`, strict `mypy` with `django-stubs`,
  `basedpyright`, `pyrefly`, and `ty`.
- **Full-suite PostgreSQL CI.** Every ORM-touching test runs against
  PostgreSQL 16 in its own CI job, on top of the SQLite matrix. Not a
  hand-picked `postgres`-marked subset.
- **Documented caveats instead of smoothed-over ones.**
  `bulk_update_or_create()` documents that Django 4.2 cannot return
  primary keys from `bulk_create(update_conflicts=True)` and that
  MySQL/MariaDB ignore `unique_fields` as a conflict target. The
  subquery aggregates document a MySQL failure on versions before
  8.0.14. The CHANGELOG has corrected itself in public before: an
  earlier release claimed `queryset_iterator` lost a memory benchmark
  outright, and a later entry retracts the claim because the
  methodology (`tracemalloc`) could not see the database driver's
  C-level result buffer and therefore could not establish it either
  way.

## What it deliberately does not do

Some features stay out because other packages already serve those
cases well:

- **No XLSX, no import, no resource classes.** `ExportMixin` is
  CSV/JSON export only, by design. For spreadsheets, round-trip
  import, or resource classes, reach for
  [django-import-export](https://django-import-export.readthedocs.io/).
  See [Export](admin-export).
- **No queryable or searchable encryption.** Fernet salts every
  encryption, so even `exact` can never match at the database level.
  Every lookup except `isnull` raises `NotImplementedError` by design.
  Filter in Python after decrypting, or maintain a separate searchable
  hash column alongside the encrypted one. See
  [Encrypted model fields](encrypted-model-fields).
