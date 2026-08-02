import gc
from collections.abc import Callable, Iterator
from typing import Any

from django.db.models import QuerySet


def queryset_iterator(
    queryset: QuerySet[Any],
    chunksize: int = 1000,
    getfunc: Callable[[Any, str], Any] = getattr,
) -> Iterator[Any]:
    """''
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

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
