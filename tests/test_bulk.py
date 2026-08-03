"""Tests for django_utils.bulk."""

import django
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


@pytest.mark.parametrize(
    'kwargs',
    [
        {'unique_fields': [], 'update_fields': ['stock']},
        {'unique_fields': ['name'], 'update_fields': []},
        {
            'unique_fields': ['name'],
            'update_fields': ['stock'],
            'batch_size': 0,
        },
    ],
)
def test_rejects_bad_arguments_even_with_empty_objs(kwargs):
    """batch_size/unique_fields/update_fields validation must run before
    the empty-objs short-circuit -- a caller passing [] alongside a bad
    batch_size or empty field list must still see the ValueError, not a
    silent []."""
    with query_debug.query_budget(warn_at=100) as budget:
        with pytest.raises(ValueError):
            bulk.bulk_update_or_create([], **kwargs)
    assert budget.count == 0


def test_rejects_mixed_models():
    with pytest.raises(ValueError):
        bulk.bulk_update_or_create(
            [_ingredient('x', 1), models.Sandwich(data={})],
            unique_fields=['name'],
            update_fields=['stock'],
        )


def test_upsert_by_pk_alias():
    existing = models.Ingredient.objects.create(name='salt', stock=1)
    bulk.bulk_update_or_create(
        [models.Ingredient(pk=existing.pk, name='salt', stock=99)],
        unique_fields=['pk'],
        update_fields=['stock'],
    )
    assert models.Ingredient.objects.get(pk=existing.pk).stock == 99


def test_multi_column_unique_constraint():
    sandwich = models.Sandwich.objects.create(data={})
    models.Review.objects.create(sandwich=sandwich, rating=5, comment='old')
    bulk.bulk_update_or_create(
        [
            models.Review(sandwich=sandwich, rating=5, comment='new'),
            models.Review(sandwich=sandwich, rating=1, comment='fresh'),
        ],
        unique_fields=['sandwich', 'rating'],
        update_fields=['comment'],
    )
    assert models.Review.objects.count() == 2
    assert (
        models.Review.objects.get(sandwich=sandwich, rating=5).comment == 'new'
    )


def test_fk_attname_accepted():
    sandwich = models.Sandwich.objects.create(data={})
    models.Review.objects.create(sandwich=sandwich, rating=5, comment='old')
    bulk.bulk_update_or_create(
        [models.Review(sandwich=sandwich, rating=5, comment='attname')],
        unique_fields=['sandwich_id', 'rating'],
        update_fields=['comment'],
    )
    assert (
        models.Review.objects.get(sandwich=sandwich, rating=5).comment
        == 'attname'
    )


def test_rejects_non_concrete_field():
    # 'review' resolves on Sandwich (reverse FK) but is not concrete;
    # bulk_create could never use it as a conflict target.
    with pytest.raises(ValueError):
        bulk.bulk_update_or_create(
            [models.Sandwich(data={})],
            unique_fields=['review'],
            update_fields=['data'],
        )


def test_pk_and_pk_name_overlap_detected():
    with pytest.raises(ValueError):
        bulk.bulk_update_or_create(
            [_ingredient('x', 1)],
            unique_fields=['pk'],
            update_fields=['id'],
        )


def test_returned_objects_pk_population():
    """Django 5.0+ populates pks on the returned objects; Django 4.2
    cannot (ticket #34698, fixed in 5.0) and returns pk=None. The module
    docstring documents exactly this split."""
    # 'salt' exists already, so the call covers a conflict-updated row
    # AND a freshly inserted one — the docstring claims both alike.
    models.Ingredient.objects.create(name='salt', stock=1)
    created = bulk.bulk_update_or_create(
        [_ingredient('salt', 5), _ingredient('pepper', 3)],
        unique_fields=['name'],
        update_fields=['stock'],
    )
    pk_expected = django.VERSION >= (5, 0)
    assert all((obj.pk is not None) is pk_expected for obj in created)
