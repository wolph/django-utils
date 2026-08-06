"""Compare queryset_iterator against QuerySet.iterator().

Run with: .venv/bin/python benchmarks/queryset_iterator.py

Reports, for each approach: wall clock, query count, process RSS
(peak resident set size), and -- for continuity with prior runs --
``tracemalloc`` peak.

Query count and wall clock are measured in separate passes. Wrapping
``time.perf_counter()`` inside ``CaptureQueriesContext`` would time
the query-logging instrumentation as well as the code under test --
overhead that scales with query count, so it would penalise the
21-query path far more than the 1-query path and skew the headline
ratio. Each ``fn`` therefore runs twice per row: once inside
``CaptureQueriesContext`` (query count only, not timed) and once
outside it (wall clock, RSS and ``tracemalloc`` peak, not counted).

Query count is the mechanism this function actually trades on: N
bounded ``LIMIT`` queries instead of 1 unbounded query. It is
reported via ``CaptureQueriesContext`` and is backend-independent
evidence, unlike memory.

RSS and ``tracemalloc`` are *not* reliable evidence of the effect
this function exists to bound. SQLite has no server-side cursor to
disable in the first place, and its stdlib driver steps rows lazily
rather than buffering the whole result set, so it cannot demonstrate
the driver-buffering failure mode this function guards against --
see the note printed at the end and
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
    """Run ``fn`` once for query count, once (separately) for timing.

    The two are measured in separate passes so that
    ``CaptureQueriesContext``'s per-query logging overhead -- which
    scales with query count -- never leaks into the wall-clock
    figure. See the module docstring.
    """
    gc.collect()
    with CaptureQueriesContext(connection) as queries:
        fn()
    query_count = len(queries)

    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    count = fn()
    elapsed = time.perf_counter() - start
    rss_high_water = _rss_mib()
    _current, py_peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(
        f'{label:<36} {count:>7} rows  {elapsed:7.3f}s  '
        f'queries={query_count:>3}  '
        f'rss_high_water={rss_high_water:7.2f} MiB '
        '[whole-process high-water, monotonic -- not comparable '
        'between rows]  '
        f'py_alloc_peak={py_peak / (1024 * 1024):6.2f} MiB '
        '[Python allocations only -- does not observe driver '
        'buffering]'
    )
    return elapsed, query_count, rss_high_water, py_peak


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
        gc_overhead_fraction = (gc_time - ours_time) / ours_time
        print(
            'gc_collect=True overhead:             '
            f'{gc_time - ours_time:+.3f}s '
            f'({gc_overhead_fraction:+.1%} added to '
            "queryset_iterator()'s default-mode wall time)"
        )
        print(
            '\nNOTE: SQLite has no server-side cursor to disable, and '
            'its stdlib driver steps rows lazily rather than '
            'buffering the whole result set, so this benchmark '
            'cannot demonstrate the driver-buffering effect '
            'queryset_iterator exists to bound -- the RSS and '
            'tracemalloc figures above are read from a backend that '
            'never buffers an unbounded result set client-side in '
            'the first place. That effect is verified on MySQL with '
            'mysqlclient (its default cursor calls store_result()); '
            'it is driver-dependent, and not established here, on '
            'Oracle and on PostgreSQL with '
            '`DISABLE_SERVER_SIDE_CURSORS = True`. The query-count '
            'comparison above is the backend-independent evidence: '
            'it shows the mechanism (N bounded queries vs. 1 '
            'unbounded query) directly, regardless of what any '
            'driver does with the result set.'
        )
    finally:
        runner.teardown_databases(old_config)


if __name__ == '__main__':
    main()
