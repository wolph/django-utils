"""Tests for django_utils.bulk."""

import pytest
from django_utils import bulk, query_debug

from tests.test_app import models

pytestmark = pytest.mark.django_db


def _ingredient(name, stock):
    return models.Ingredient(name=name, stock=stock)


def test_creates_new_rows():
    created = bulk.bulk_update_or_create(
        [_ingredient('salt', 5), _ingredient('pepper', 3)],
        unique_fields=['name'],
        update_fields=['stock'],
    )
    assert len(created) == 2
    assert models.Ingredient.objects.count() == 2


def test_updates_existing_rows_without_duplicating():
    models.Ingredient.objects.create(name='salt', stock=1)
    bulk.bulk_update_or_create(
        [_ingredient('salt', 10)],
        unique_fields=['name'],
        update_fields=['stock'],
    )
    assert models.Ingredient.objects.count() == 1
    assert models.Ingredient.objects.get(name='salt').stock == 10


def test_mixed_create_and_update():
    models.Ingredient.objects.create(name='salt', stock=1)
    result = bulk.bulk_update_or_create(
        [_ingredient('salt', 2), _ingredient('cumin', 7)],
        unique_fields=['name'],
        update_fields=['stock'],
    )
    assert len(result) == 2
    assert models.Ingredient.objects.count() == 2
    assert models.Ingredient.objects.get(name='salt').stock == 2


def test_batching_issues_one_query_per_chunk():
    objs = [_ingredient(f'i{n}', n) for n in range(5)]
    with query_debug.query_budget(warn_at=100) as budget:
        bulk.bulk_update_or_create(
            objs,
            unique_fields=['name'],
            update_fields=['stock'],
            batch_size=2,
        )
    assert budget.count == 3  # ceil(5 / 2)
    assert models.Ingredient.objects.count() == 5


def test_empty_input_is_a_noop():
    with query_debug.query_budget(warn_at=100) as budget:
        assert (
            bulk.bulk_update_or_create(
                [], unique_fields=['name'], update_fields=['stock']
            )
            == []
        )
    assert budget.count == 0


@pytest.mark.parametrize(
    'kwargs',
    [
        {'unique_fields': [], 'update_fields': ['stock']},
        {'unique_fields': ['name'], 'update_fields': []},
        {'unique_fields': ['name'], 'update_fields': ['name']},
        {'unique_fields': ['name'], 'update_fields': ['nonexistent']},
        {
            'unique_fields': ['name'],
            'update_fields': ['stock'],
            'batch_size': 0,
        },
    ],
)
def test_rejects_bad_arguments(kwargs):
    with pytest.raises(ValueError):
        bulk.bulk_update_or_create([_ingredient('x', 1)], **kwargs)


def test_rejects_mixed_models():
    with pytest.raises(ValueError):
        bulk.bulk_update_or_create(
            [_ingredient('x', 1), models.Sandwich(data={})],
            unique_fields=['name'],
            update_fields=['stock'],
        )
