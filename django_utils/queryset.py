import gc
from collections.abc import Callable, Iterator
from typing import Any

from django.db.models import QuerySet


def queryset_iterator(
    queryset: QuerySet[Any],
    chunksize: int = 1000,
    getfunc: Callable[[Any, str], Any] = getattr,
) -> Iterator[Any]:
    """Iterate over a Django queryset in fixed-size chunks, ordered by pk.

    Uses keyset pagination (``WHERE pk > last_seen_pk LIMIT chunksize``)
    instead of a database cursor, so each chunk is fetched as its own
    independent query rather than as part of one long-lived cursor kept
    open for the whole iteration.

    Benchmarked (``benchmarks/queryset_iterator.py``) against
    ``QuerySet.iterator(chunk_size=...)`` on SQLite -- 20,000 rows,
    chunksize=1000, 5 runs -- this function was consistently *slower*,
    not faster: ~1.6x the wall-clock time (1.57x-1.70x across runs) and
    ~1.85x the peak traced memory. Roughly 30-38% of the wall-clock gap
    is the ``gc.collect()`` call made after every chunk (a fixable
    implementation detail, not an inherent cost of keyset pagination);
    without it the gap narrows to near parity (1.06x-1.16x) but never
    turns into a win. SQLite has no server-side cursor support, so this
    is the backend most favourable to this function's approach, and it
    still lost: Django's ``iterator(chunk_size=...)`` already fetches
    rows from the cursor in bounded batches even without one, giving it
    the same "don't load everything into memory" property via a single
    query instead of one query per chunk.

    Prefer ``QuerySet.iterator(chunk_size=...)`` in the general case --
    it is simpler and was not slower on any backend measured here.
    Reach for this function instead when a single long-lived query is
    specifically undesirable: because each chunk is issued as a new
    query rather than read from one cursor held open for the whole
    iteration, iteration can pick back up on a connection that was
    reset or recycled between chunks, which a single open cursor
    cannot.

    Note that the results are always ordered by the primary key.
    """
    pk: Any = None
    queryset = queryset.order_by('pk')

    while True:
        chunk = queryset if pk is None else queryset.filter(pk__gt=pk)
        rows = list(chunk[:chunksize])
        if not rows:
            return

        for row in rows:
            pk = getfunc(row, 'pk')
            yield row

        gc.collect()
