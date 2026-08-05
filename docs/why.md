# Why django-utils2

An evidence-based case, not a marketing pitch: django-utils2 grew
where an incumbent stopped maintaining its answer, or never had one —
ASGI-safe request context where `django-crum` still relies on
thread-locals, production-safe N+1 detection where `nplusone` stopped
shipping releases in 2018. This page lays out that evidence and what
the library holds itself to in exchange — engineer to engineer, every
claim below sourced from this repository itself (README, CHANGELOG, or
the CI/tox configuration that enforces it).

## Where the incumbents fall short

| Incumbent | Where it falls short | This library's answer |
| --- | --- | --- |
| `django-crum` | Stores the current request/user in a thread-local. Under ASGI, one thread's event loop interleaves many concurrent requests as asyncio tasks, so a thread-local leaks state between them. | `django_utils.context.RequestContextMiddleware` uses `contextvars.ContextVar` — isolated per asyncio task, correct under both WSGI and ASGI. See [Current request / user (ASGI-safe)](middleware.md). |
| `nplusone` | The dominant N+1-detection package for Django; unmaintained since 2018. | `django_utils.query_debug.query_budget` counts queries via Django's own `connection.execute_wrapper()` — production-safe (works with `DEBUG` off), usable in real request paths, not only in tests or a dev-only debug toolbar. See [Query budgets](middleware.md). |

## What this library holds itself to

- **CSP-safe markup everywhere.** The JSON widget and the
  dropdown/select2 admin filters ship as small vanilla-JS assets with
  no inline handlers, no inline `<script>`, and no inline `style=`.
  That's a fixed guarantee, not an original one: 4.1.0's changelog
  records that `dropdown_filter.html` and `select2_filter.html` used
  to emit an inline `onchange` handler, an inline `style=` attribute,
  and an inline `<script>` before this release removed all three. The
  same rule is enforced on the docs site's own live demo pages by a
  dedicated test (`tests/test_docs_demos.py`).
- **100% test coverage, including templates.** `django-coverage-plugin`
  measures the shipped `.html` templates as part of the same
  `coverage report --fail-under=100` gate as the Python code, so an
  unrendered template line fails CI instead of being invisible to
  coverage.py.
- **Six type checkers and linters, every CI run.** `ruff check`,
  `ruff format --check`, `mypy` (strict, with `django-stubs`),
  `basedpyright`, `pyrefly`, and `ty` — each its own tox environment,
  run as dedicated CI jobs (`tox -e lint` and
  `tox -e mypy,basedpyright,pyrefly,ty`).
- **Full-suite PostgreSQL CI**, not a hand-picked subset. Every
  ORM-touching test — not only the ones carrying the `postgres` pytest
  marker — runs against PostgreSQL 16 in its own CI job, on top of the
  SQLite matrix.
- **Backend/version honesty, in the documentation itself.** Caveats
  are written down, not smoothed over: `bulk_update_or_create()`
  documents that Django 4.2 can't return primary keys from
  `bulk_create(update_conflicts=True)` (fixed in 5.0), and that
  MySQL/MariaDB's `ON DUPLICATE KEY UPDATE` ignores `unique_fields` as
  a conflict target where PostgreSQL/SQLite honour it; the subquery
  aggregates document a MySQL-only failure on versions before 8.0.14.
  The CHANGELOG has corrected its own claim in public before: an
  earlier release concluded, from a benchmark that couldn't actually
  measure the effect, that `queryset_iterator` lost outright to
  `QuerySet.iterator()`; a later entry retracts that conclusion,
  explains why the benchmark methodology (`tracemalloc`, which can't
  see a database driver's C-level result buffer) couldn't establish it
  either way, and republishes the corrected story instead of quietly
  editing history.

## Comparison

django-utils2 also holds a hard line around what it deliberately does
not do — not for lack of ambition, but because other packages already
serve those cases well:

- **No XLSX, no import, no resource classes.** `ExportMixin` is
  CSV/JSON export only, by design. For spreadsheets, round-trip
  import, or resource classes, reach for
  [django-import-export](https://django-import-export.readthedocs.io/).
  See [Export](admin-export).
- **No queryable or searchable encryption.** Fernet salts every
  encryption, so even `exact` can never match at the database level —
  every lookup except `isnull` raises `NotImplementedError` by design.
  Filter in Python after decrypting, or maintain a separate searchable
  hash column alongside the encrypted one. See
  [Encrypted model fields](encrypted-model-fields).
