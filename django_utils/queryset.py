import gc
from collections.abc import Callable, Generator
from typing import Any

from django.db.models import QuerySet


def queryset_iterator(
    queryset: QuerySet[Any],
    chunksize: int = 1000,
    getfunc: Callable[[Any, str], Any] = getattr,
    *,
    pk_field: str = 'pk',
    start_after: Any = None,
    gc_collect: bool = False,
) -> Generator[Any, None, None]:
    """Iterate over a Django queryset in fixed-size chunks.

    Uses keyset pagination (``WHERE <pk_field> > <cursor> LIMIT
    chunksize``) instead of a database cursor: each chunk is fetched
    as its own independent query rather than as part of one
    long-lived cursor kept open for the whole iteration. The database
    driver therefore never has to hold more than one chunk's worth of
    rows at a time -- whatever the driver does internally, it does it
    ``chunksize`` rows at a time.

    Why this function exists
        ``QuerySet.iterator(chunk_size=...)`` issues a single,
        unbounded query and reads it back in batches of
        ``chunk_size``. On PostgreSQL, with server-side cursors
        enabled (Django's default), that single query uses a
        server-side cursor: the *database* holds the unfetched rows,
        not the driver, so ``iterator()`` is the better choice there
        -- one query, bounded client memory, less code. But Django
        only opens a server-side cursor on PostgreSQL. On MySQL with
        mysqlclient, the default cursor calls ``store_result()`` and
        materialises the *entire* result set client-side before
        Python sees the first row, in a C buffer that ``chunk_size``
        never touches -- this is verified. Oracle (``python-oracledb``)
        and PostgreSQL with ``DISABLE_SERVER_SIDE_CURSORS = True`` are
        driver-dependent: they may also buffer the full result set
        client-side, but that is not established the way mysqlclient's
        behaviour is. SQLite has no server-side cursor to disable
        either, but the stdlib ``sqlite3`` module steps rows lazily
        rather than buffering the whole result set (see the benchmark
        section below). Where a driver does buffer the whole result
        set, ``iterator()``'s peak memory is set by the driver, not by
        ``chunk_size``, and a large enough table can exhaust it. This
        function exists because that failure was written after
        ``QuerySet.iterator()`` exhausted memory on a very large
        table: splitting one unbounded query into many ``LIMIT``-ed
        queries means the driver never receives more than one chunk at
        a time, regardless of backend. The cost is real: N small
        queries instead of 1, plus a modest wall-clock overhead (see
        below).

    Benchmark (``benchmarks/queryset_iterator.py``), SQLite, 20,000
    rows, chunksize=1000
        Wall clock is close to parity with ``QuerySet.iterator()``
        (~1.09x-1.14x across runs; query count and wall clock are
        measured in separate passes so that query-logging
        instrumentation doesn't inflate the many-query path's timing
        more than the single-query path's). An earlier version of
        this function called ``gc.collect()`` after every chunk; that
        call alone added roughly 37-47% to ``queryset_iterator()``'s
        default-mode wall-clock time for no measured reduction in
        Python-level memory, so it is off by default here (see
        ``gc_collect`` below).

        The benchmark's ``tracemalloc`` peak figures are *not*
        evidence about the memory story either way: ``tracemalloc``
        only sees Python-level allocations, so it cannot see a
        driver's C-level result buffer -- the thing this function
        exists to bound. SQLite also has no server-side cursor to
        disable in the first place, and its stdlib driver does not
        buffer the full result set either, so it structurally cannot
        reproduce the failure mode this function guards against. That
        failure mode is verified on MySQL with mysqlclient, and may
        also occur -- driver-dependent, not established here -- on
        Oracle and on PostgreSQL with
        ``DISABLE_SERVER_SIDE_CURSORS = True``; it does not occur on
        SQLite, and none of this shows up in a ``tracemalloc`` trace
        on any backend. No OOM has been measured here; the claim is
        narrower: bounded driver-side memory by construction, not a
        demonstrated fix for a specific crash.

    Choosing between the two
        Prefer ``QuerySet.iterator(chunk_size=...)`` on PostgreSQL
        with server-side cursors enabled (the default): one query,
        and the database -- not the driver -- holds the unfetched
        rows. Reach for this function when that guarantee isn't
        available (MySQL, Oracle, SQLite, or PostgreSQL with
        server-side cursors disabled), where a single unbounded query
        can hand the driver an unbounded buffer. It is also useful
        whenever a single long-lived query/cursor is undesirable for
        another reason: because each chunk is its own query,
        iteration can resume on a connection that was reset or
        recycled between chunks, which one open cursor cannot.

    Keyword-only options

    ``pk_field``
        Column to order and paginate by, instead of the primary key.
        Must be unique, indexed, totally ordered and non-nullable so
        keyset pagination doesn't skip or repeat rows -- e.g. a
        monotonic ``created_at`` or integer ``id`` column. Useful when
        the primary key itself is a randomly-ordered UUID that would
        make every ``WHERE pk > cursor`` query scan out of index
        order. A ``NULL`` value read from ``pk_field`` raises
        ``ValueError``, since the keyset cursor cannot resume from
        ``NULL``. A non-unique value silently truncates: if several
        rows tie on the same ``pk_field`` value, only the ones that
        land in the current chunk are yielded and the rest of that
        tied group is skipped.

    ``start_after``
        Resume from a previously-seen cursor value instead of
        starting from the beginning, so a batch job that died
        partway through can continue rather than restart. When given,
        the first chunk is filtered ``> start_after`` instead of
        being unfiltered. The value must be a value of ``pk_field``
        (a plain pk by default)::

            last_seen = None
            for row in queryset_iterator(
                MyModel.objects.all(),
                pk_field='created_at',
                start_after=last_seen,
            ):
                process(row)
                last_seen = row.created_at
                checkpoint(last_seen)  # survives a restart

    ``gc_collect``
        Call ``gc.collect()`` after every chunk. Off by default: in
        the SQLite benchmark above it adds roughly 37-47% to this
        function's default-mode wall-clock time and made no measured
        difference to peak Python-level memory. It is available for
        runs where reclaiming Python-level garbage more aggressively
        than the allocator would on its own is worth that cost --
        e.g. very large runs where resident set size matters more
        than throughput.

    Note that the results are always ordered by ``pk_field``.
    """
    if chunksize < 1:
        raise ValueError(f'chunksize must be >= 1, got {chunksize!r}')

    cursor: Any = start_after
    queryset = queryset.order_by(pk_field)

    while True:
        chunk = (
            queryset
            if cursor is None
            else queryset.filter(**{f'{pk_field}__gt': cursor})
        )
        rows = list(chunk[:chunksize])
        if not rows:
            return

        for row in rows:
            cursor = getfunc(row, pk_field)
            if cursor is None:
                raise ValueError(
                    f'pk_field={pk_field!r} is NULL on a row: '
                    'queryset_iterator requires pk_field to be '
                    'non-nullable, since a NULL cursor cannot be '
                    'used to resume keyset pagination.'
                )
            yield row

        if gc_collect:
            gc.collect()
