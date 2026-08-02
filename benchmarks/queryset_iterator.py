"""Compare queryset_iterator against QuerySet.iterator().

Run with: .venv/bin/python benchmarks/queryset_iterator.py

Times only the iteration itself (row setup happens outside the timed
block) and records peak memory via tracemalloc alongside wall clock,
since memory stability -- not raw speed -- is the claim under test.
A third run strips queryset_iterator's per-chunk gc.collect() call so
that overhead can be reported separately instead of hiding inside the
headline ratio.
"""

import gc
import os
import time
import tracemalloc
from collections.abc import Callable, Iterator

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django  # noqa: E402

django.setup()

from django.contrib.contenttypes.models import ContentType  # noqa: E402
from django.db.models import QuerySet  # noqa: E402
from django.test.runner import DiscoverRunner  # noqa: E402
from django.test.utils import setup_test_environment  # noqa: E402
from django_utils.queryset import queryset_iterator  # noqa: E402

ROWS = 20_000
CHUNKSIZE = 1000


def _queryset_iterator_no_gc(
    queryset: QuerySet[ContentType], chunksize: int = CHUNKSIZE
) -> Iterator[ContentType]:
    """queryset_iterator with the per-chunk gc.collect() call removed.

    Isolates how much of queryset_iterator's cost is the gc.collect()
    call itself versus the keyset-pagination strategy.
    """
    pk = None
    queryset = queryset.order_by('pk')
    while True:
        chunk = queryset if pk is None else queryset.filter(pk__gt=pk)
        rows = list(chunk[:chunksize])
        if not rows:
            return
        for row in rows:
            pk = row.pk
            yield row


def _measure(label: str, fn: Callable[[], int]) -> tuple[float, int]:
    gc.collect()
    tracemalloc.start()
    start = time.perf_counter()
    count = fn()
    elapsed = time.perf_counter() - start
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    print(
        f'{label:<32} {count:>7} rows  {elapsed:7.3f}s  '
        f'peak={peak / (1024 * 1024):7.2f} MiB'
    )
    return elapsed, peak


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

        core_time, core_peak = _measure(
            'QuerySet.iterator()',
            lambda: sum(
                1
                for _ in ContentType.objects.all().iterator(
                    chunk_size=CHUNKSIZE
                )
            ),
        )
        ours_time, ours_peak = _measure(
            'queryset_iterator()',
            lambda: sum(
                1 for _ in queryset_iterator(ContentType.objects.all())
            ),
        )
        no_gc_time, _no_gc_peak = _measure(
            'queryset_iterator() [no gc]',
            lambda: sum(
                1 for _ in _queryset_iterator_no_gc(ContentType.objects.all())
            ),
        )

        print(
            f'\nratio (ours/core), wall clock:  {ours_time / core_time:.2f}x'
        )
        print(f'ratio (ours/core), peak memory: {ours_peak / core_peak:.2f}x')
        print(
            f'gc.collect() overhead:          '
            f'{ours_time - no_gc_time:+.3f}s '
            f'({(ours_time - no_gc_time) / ours_time:+.1%} of ours), '
            f'no-gc ratio (ours/core): {no_gc_time / core_time:.2f}x'
        )
    finally:
        runner.teardown_databases(old_config)


if __name__ == '__main__':
    main()
