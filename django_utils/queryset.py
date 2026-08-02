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
    chunksize=1000 -- this function is close to parity on wall-clock
    time (~1.09x-1.14x across runs) but still uses ~1.85x-1.88x the peak
    traced memory. SQLite has no server-side cursor support, so this is
    the backend most favourable to this function's approach, and it
    still didn't win: Django's ``iterator(chunk_size=...)`` already
    fetches rows from the cursor in bounded batches even without one,
    giving it the same "don't load everything into memory" property via
    a single query instead of one query per chunk.

    An earlier version of this function called ``gc.collect()`` after
    every chunk, which is why the wall-clock ratio above used to read
    ~1.6x (1.57x-1.70x across runs) rather than ~1.1x: that call alone
    accounted for 27-31% of the wall-clock gap against
    ``QuerySet.iterator()``, while making no measurable difference to
    peak memory (0.74 vs 0.75 MiB with it removed). It was dropped.

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
