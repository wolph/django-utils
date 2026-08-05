# QuerySets & bulk

ORM helpers for two places naive Django code burns memory or produces
wrong numbers: `queryset_iterator` bounds memory on both the client
and the database while iterating millions of rows, `Subquery`-based
aggregates avoid the JOIN fan-out that silently multiplies
`annotate(Count(...))` results when combined, and
`bulk_update_or_create` upserts in one statement per batch instead of
two racy queries per row.

## queryset_iterator

## Subquery aggregates

## Bulk upsert
