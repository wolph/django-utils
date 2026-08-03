"""Shared pytest configuration for the test suite.

Registers the ``postgres`` marker for tests that require a real
PostgreSQL backend (there are none yet -- this is ahead of Phase E's
PostgreSQL-only ENUM field) and auto-skips anything carrying it unless
the suite is actually running against PostgreSQL. See
``tests/settings.py`` (``DJANGO_UTILS_TEST_POSTGRES``) and the
``postgres`` tox env / CI job -- both of which run the *full* suite
against PostgreSQL rather than only ``postgres``-marked tests; this
marker exists for future backend-specific tests, not as the thing that
currently selects what runs there.
"""

import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        'markers',
        'postgres: requires a real PostgreSQL backend '
        '(DJANGO_UTILS_TEST_POSTGRES=1); skipped otherwise.',
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if os.environ.get('DJANGO_UTILS_TEST_POSTGRES'):
        return
    skip_postgres = pytest.mark.skip(
        reason='requires DJANGO_UTILS_TEST_POSTGRES=1 (real PostgreSQL)'
    )
    for item in items:
        if 'postgres' in item.keywords:
            item.add_marker(skip_postgres)
