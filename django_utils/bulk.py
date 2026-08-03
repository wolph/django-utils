"""Bulk upsert built on Django's native conflict handling.

``bulk_update_or_create`` wraps ``bulk_create(update_conflicts=True)``
(Django 4.1+) with chunking and up-front validation.  Unlike a loop of
``update_or_create`` (2N queries, racy between check and write), the
upsert happens in one ``INSERT ... ON CONFLICT DO UPDATE`` statement per
batch, atomic per row on the database side.

Backend honesty: PostgreSQL and SQLite use ``ON CONFLICT`` with
``unique_fields`` naming the conflict target; MySQL/MariaDB use
``ON DUPLICATE KEY UPDATE``, which ignores ``unique_fields`` and fires
on *any* unique constraint — identical behaviour when the model has one
unique constraint, subtly broader when it has several.
"""

import typing
from collections.abc import Iterable, Sequence

from django.db import models

M = typing.TypeVar('M', bound=models.Model)


def bulk_update_or_create(
    objs: Iterable[M],
    *,
    unique_fields: Sequence[str],
    update_fields: Sequence[str],
    batch_size: int = 1000,
) -> list[M]:
    """Insert ``objs``, updating ``update_fields`` on conflicts.

    Rows whose ``unique_fields`` already exist are updated instead of
    raising ``IntegrityError``; new rows are inserted.  Returns the
    input objects as a list.  All validation errors raise ``ValueError``
    before any query runs.
    """
    items = list(objs)
    if not items:
        return []
    if batch_size < 1:
        raise ValueError(f'batch_size must be >= 1, got {batch_size!r}')
    if not unique_fields:
        raise ValueError('unique_fields must not be empty')
    if not update_fields:
        raise ValueError('update_fields must not be empty')
    overlap = set(unique_fields) & set(update_fields)
    if overlap:
        raise ValueError(
            f'fields cannot be in both unique_fields and '
            f'update_fields: {sorted(overlap)}'
        )
    model = type(items[0])
    mixed = [obj for obj in items if type(obj) is not model]
    if mixed:
        raise ValueError(
            f'all objects must be {model.__name__}, '
            f'got {type(mixed[0]).__name__}'
        )
    valid_fields = {field.name for field in model._meta.concrete_fields}
    unknown = (set(unique_fields) | set(update_fields)) - valid_fields
    if unknown:
        raise ValueError(
            f'unknown fields for {model.__name__}: {sorted(unknown)}'
        )

    manager = model._base_manager
    result: list[M] = []
    for start in range(0, len(items), batch_size):
        result.extend(
            manager.bulk_create(
                items[start : start + batch_size],
                update_conflicts=True,
                unique_fields=list(unique_fields),
                update_fields=list(update_fields),
            )
        )
    return result
