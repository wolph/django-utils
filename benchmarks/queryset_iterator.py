"""Compare queryset_iterator against QuerySet.iterator().

Run with: .venv/bin/python benchmarks/queryset_iterator.py

Reports, for each approach: wall clock, query count, process RSS
(peak resident set size), and -- for continuity with prior runs --
``tracemalloc`` peak.

Query count is the mechanism this function actually trades on: N
bounded ``LIMIT`` queries instead of 1 unbounded query. It is
reported via ``CaptureQueriesContext`` and is backend-independent
evidence, unlike memory.

RSS and ``tracemalloc`` are *not* reliable evidence of the effect
this function exists to bound. SQLite has no server-side cursor to
disable in the first place, so it cannot demonstrate the
driver-buffering failure mode this function guards against -- see
the note printed at the end and
``django_utils.queryset.queryset_iterator``'s docstring. They are
reported anyway for continuity with earlier runs, clearly labelled.
"""

import gc
import os
import platform
import resource
import time
import tracemalloc
from collections.abc import Callable

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django  # noqa: E402

django.setup()

from django.contrib.contenttypes.models import ContentType  # noqa: E402
from django.db import connection  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402
from django.test.utils import (  # noqa: E402
    CaptureQueriesContext,
    setup_test_environment,
)
from django_utils.queryset import queryset_iterator  # noqa: E402

ROWS = 20_000
CHUNKSIZE = 1000

# ru_maxrss is bytes on macOS/BSD, kilobytes on Linux -- normalise to
# bytes so the printed MiB figure means the same thing on either.
_RU_MAXRSS_UNIT_BYTES = 1 if platform.system() == 'Darwin' else 1024


def _rss_mib() -> float:
    """Return the process's peak RSS *so far*, in MiB.

    ``ru_maxrss`` is a whole-process high-water mark that only ever
    grows -- it is not a delta for the block just measured. A later
    measurement that doesn't exceed an earlier one's peak will report
    that earlier peak, not evidence the later block used less.
    """
    raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return raw * _RU_MAXRSS_UNIT_BYTES / (1024 * 1024)


def _measure(
    label: str, fn: Callable[[], int]
) -> tuple[float, int, float, int]:
    gc.collect()
    tracemalloc.start()
    with CaptureQueriesContext(connection) as queries:
        start = time.perf_counter()
        count = fn()
        elapsed = time.perf_counter() - start
    rss_high_water = _rss_mib()
    _current, py_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        f'{label:<36} {count:>7} rows  {elapsed:7.3f}s  '
        f'queries={len(queries):>3}  '
        f'rss_high_water={rss_high_water:7.2f} MiB  '
        f'py_alloc_peak={py_peak / (1024 * 1024):6.2f} MiB '
        '[Python allocations only -- does not observe driver '
        'buffering]'
    )
    return elapsed, len(queries), rss_high_water, py_peak


def main() -> None:
    setup_test_environment()
    runner = DiscoverRunner(verbosity=0)
    old_config = runner.setup_databases()
    try:
        ContentType.objects.all().delete()
        ContentType.objects.bulk_create(
            ContentType(app_label=f'app{i}', model=f'model{i}')
            for i in range(ROWS)
        )

        core_time, core_queries, _core_rss, core_py_peak = _measure(
            'QuerySet.iterator()',
            lambda: sum(
                1
                for _ in ContentType.objects.all().iterator(
                    chunk_size=CHUNKSIZE
                )
            ),
        )
        ours_time, ours_queries, _ours_rss, ours_py_peak = _measure(
            'queryset_iterator()',
            lambda: sum(
                1 for _ in queryset_iterator(ContentType.objects.all())
            ),
        )
        gc_time, gc_queries, _gc_rss, _gc_py_peak = _measure(
            'queryset_iterator(gc_collect=True)',
            lambda: sum(
                1
                for _ in queryset_iterator(
                    ContentType.objects.all(), gc_collect=True
                )
            ),
        )

        print(
            f'\nquery count -- the mechanism, backend-independent:\n'
            f'  QuerySet.iterator():                {core_queries:>4} '
            f'query\n'
            f'  queryset_iterator():                 {ours_queries:>4} '
            f'queries\n'
            f'  queryset_iterator(gc_collect=True):  {gc_queries:>4} '
            f'queries'
        )
        print(
            '\nratio (ours/core), wall clock:        '
            f'{ours_time / core_time:.2f}x'
        )
        print(
            'ratio (ours/core), tracemalloc peak:  '
            f'{ours_py_peak / core_py_peak:.2f}x '
            '[Python allocations only]'
        )
        print(
            'gc_collect=True overhead vs default:  '
            f'{gc_time - ours_time:+.3f}s '
            f'({(gc_time - ours_time) / ours_time:+.1%})'
        )
        print(
            '\nNOTE: SQLite has no server-side cursor to disable, so '
            'this benchmark cannot demonstrate the driver-buffering '
            'effect queryset_iterator exists to bound -- the RSS and '
            'tracemalloc figures above are read from a backend that '
            'never buffers an unbounded result set client-side in the '
            'first place. That effect appears on MySQL and Oracle '
            '(whose drivers buffer the full result set client-side by '
            'default) and on PostgreSQL when '
            '`DISABLE_SERVER_SIDE_CURSORS = True`. The query-count '
            'comparison above is the backend-independent evidence: it '
            'shows the mechanism (N bounded queries vs. 1 unbounded '
            'query) directly, regardless of what any driver does with '
            'the result set.'
        )
    finally:
        runner.teardown_databases(old_config)


if __name__ == '__main__':
    main()
