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

Version honesty: on Django 5.0+ the returned objects have their primary
keys populated (inserted and conflict-updated rows alike) — where the
backend can return rows from a bulk insert at all: PostgreSQL and
SQLite can, MariaDB can, vanilla MySQL never can (its Django backend
disables row-returning inserts on every Django version).  On Django
4.2, ``bulk_create(update_conflicts=True)`` cannot return IDs anywhere
(Django ticket #34698, fixed in 5.0), so every returned object has
``pk=None`` even though its row was written.

Field names accept the same spellings ``bulk_create`` does: field names
(``owner``), foreign-key attnames (``owner_id``), and the ``'pk'``
alias.
"""

import typing
from collections.abc import Iterable, Sequence

from django.core import exceptions
from django.db import models

M = typing.TypeVar('M', bound=models.Model)


def _resolve_fields(
    model: type[models.Model], names: Sequence[str]
) -> set['models.Field[typing.Any, typing.Any]']:
    """Resolve field names the way ``bulk_create`` does.

    Accepts the ``'pk'`` alias and foreign-key attnames; raises
    ``ValueError`` for anything unknown or non-concrete, so the caller
    fails before any query instead of deep inside SQL compilation.
    """
    resolved: set[models.Field[typing.Any, typing.Any]] = set()
    for name in names:
        field_name = model._meta.pk.name if name == 'pk' else name
        try:
            field = model._meta.get_field(field_name)
        except exceptions.FieldDoesNotExist:
            raise ValueError(
                f'unknown field {name!r} for {model.__name__}'
            ) from None
        if not getattr(field, 'concrete', False):
            raise ValueError(
                f'{name!r} is not a concrete field on {model.__name__}'
            )
        resolved.add(
            typing.cast('models.Field[typing.Any, typing.Any]', field)
        )
    return resolved


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
    model = type(items[0])
    mixed = [obj for obj in items if type(obj) is not model]
    if mixed:
        raise ValueError(
            f'all objects must be {model.__name__}, '
            f'got {type(mixed[0]).__name__}'
        )
    # Resolve before comparing: 'pk' and the pk's real name (or an FK
    # name and its attname) must count as the same field.
    unique_resolved = _resolve_fields(model, unique_fields)
    update_resolved = _resolve_fields(model, update_fields)
    overlap = unique_resolved & update_resolved
    if overlap:
        raise ValueError(
            f'fields cannot be in both unique_fields and update_fields: '
            f'{sorted(field.name for field in overlap)}'
        )

    # django-stubs types _base_manager (so a cast is redundant for mypy),
    # but pyrefly runs without the plugin and can't see it.
    manager = model._base_manager  # pyrefly: ignore[missing-attribute]
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
