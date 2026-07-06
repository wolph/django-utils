import gc


def queryset_iterator(queryset, chunksize=1000, getfunc=getattr):
    '''''
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered
    query sets.
    '''
    pk = 0

    try:
        '''In the case of an empty list, return'''
        last_pk = getfunc(queryset.order_by('-pk')[0], 'pk')
    except IndexError:
        return

    queryset = queryset.order_by('pk')
    while pk < last_pk:
        for row in queryset.filter(pk__gt=pk)[:chunksize]:
            pk = getfunc(row, 'pk')
            yield row
        gc.collect()
