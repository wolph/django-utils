from typing import Any

import pytest
from django_utils import queryset


def _make_content_types(count: int) -> list[Any]:
    from django.contrib.contenttypes import models

    models.ContentType.objects.all().delete()
    models.ContentType.objects.bulk_create(
        models.ContentType(app_label=f'app{i}', model=f'model{i}')
        for i in range(count)
    )
    return list(models.ContentType.objects.all())


@pytest.mark.django_db()
def test_empty_queryset():
    from django.contrib.auth import models

    for user in queryset.queryset_iterator(models.User.objects.all()):
        pass


@pytest.mark.django_db()
def test_full_queryset():
    from django.contrib.contenttypes import models

    for user in queryset.queryset_iterator(models.ContentType.objects.all()):
        pass


@pytest.mark.django_db()
def test_iterator_yields_rows_with_non_positive_pks():
    from django.contrib.contenttypes import models

    # Migrations pre-populate ContentType via post_migrate, so clear it
    # first to avoid colliding with those pks (see the neighbouring test).
    models.ContentType.objects.all().delete()
    models.ContentType.objects.create(pk=-2, app_label='x', model='a')
    models.ContentType.objects.create(pk=1, app_label='x', model='b')

    pks = [
        row.pk
        for row in queryset.queryset_iterator(models.ContentType.objects.all())
    ]
    assert -2 in pks, 'row with a negative pk was silently skipped'
    assert 1 in pks


@pytest.mark.django_db()
def test_iterator_yields_rows_when_all_pks_are_negative():
    from django.contrib.contenttypes import models

    models.ContentType.objects.all().delete()
    models.ContentType.objects.create(pk=-3, app_label='x', model='a')
    models.ContentType.objects.create(pk=-1, app_label='x', model='b')

    pks = [
        row.pk
        for row in queryset.queryset_iterator(models.ContentType.objects.all())
    ]
    assert sorted(pks) == [-3, -1]


@pytest.mark.django_db()
def test_positional_args_still_work_with_default_chunksize():
    """``queryset_iterator(qs)`` -- the original call shape -- is unchanged."""
    rows = _make_content_types(5)
    result = list(queryset.queryset_iterator(rows[0].__class__.objects.all()))
    assert sorted(row.pk for row in result) == sorted(row.pk for row in rows)


@pytest.mark.django_db()
def test_positional_args_still_work_with_chunksize():
    """``queryset_iterator(qs, chunksize)`` -- second positional arg."""
    rows = _make_content_types(7)
    result = list(
        queryset.queryset_iterator(rows[0].__class__.objects.all(), 3)
    )
    assert sorted(row.pk for row in result) == sorted(row.pk for row in rows)


@pytest.mark.django_db()
def test_positional_args_still_work_with_getfunc():
    """``queryset_iterator(qs, chunksize, getfunc)`` -- all positional."""
    rows = _make_content_types(7)
    result = list(
        queryset.queryset_iterator(rows[0].__class__.objects.all(), 3, getattr)
    )
    assert sorted(row.pk for row in result) == sorted(row.pk for row in rows)


@pytest.mark.django_db()
def test_pk_field_iterates_by_non_pk_unique_column():
    """``pk_field`` orders and paginates by a unique non-pk column."""
    from django.contrib.auth import models as auth_models

    auth_models.User.objects.all().delete()
    usernames = ['charlie', 'alice', 'echo', 'bravo', 'delta']
    for name in usernames:
        auth_models.User.objects.create(username=name)

    result = [
        row.username
        for row in queryset.queryset_iterator(
            auth_models.User.objects.all(), 2, pk_field='username'
        )
    ]

    # Order follows the chosen column, not insertion/pk order.
    assert result == sorted(usernames)
    # Completeness: every row is present exactly once.
    assert len(result) == len(usernames)


@pytest.mark.django_db()
def test_start_after_filters_out_rows_at_or_before_cursor():
    """Only rows strictly after ``start_after`` are yielded."""
    rows = _make_content_types(20)
    all_pks = sorted(row.pk for row in rows)
    cursor = all_pks[9]

    result_pks = [
        row.pk
        for row in queryset.queryset_iterator(
            rows[0].__class__.objects.all(), 5, start_after=cursor
        )
    ]

    assert result_pks == all_pks[10:]
    assert cursor not in result_pks


@pytest.mark.django_db()
def test_start_after_resume_covers_whole_set_without_duplicates_or_gaps():
    """Resuming twice with ``start_after`` covers the set exactly once."""
    rows = _make_content_types(23)
    all_pks = sorted(row.pk for row in rows)
    model_cls = rows[0].__class__

    first_iterator = queryset.queryset_iterator(model_cls.objects.all(), 5)
    first_pass_pks = [next(first_iterator).pk for _ in range(10)]
    first_iterator.close()

    second_iterator = queryset.queryset_iterator(
        model_cls.objects.all(), 5, start_after=first_pass_pks[-1]
    )
    second_pass_pks = [next(second_iterator).pk for _ in range(8)]
    second_iterator.close()

    third_pass_pks = [
        row.pk
        for row in queryset.queryset_iterator(
            model_cls.objects.all(), 5, start_after=second_pass_pks[-1]
        )
    ]

    combined = first_pass_pks + second_pass_pks + third_pass_pks
    assert combined == all_pks, 'resume must cover the set with no gaps'
    assert len(combined) == len(set(combined)), 'no row yielded twice'


@pytest.mark.django_db()
def test_gc_collect_true_calls_gc_collect_once_per_chunk(monkeypatch):
    """``gc_collect=True`` calls ``gc.collect()`` after every chunk."""
    _make_content_types(12)
    calls = 0

    def fake_collect() -> int:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(queryset.gc, 'collect', fake_collect)

    from django.contrib.contenttypes import models

    list(
        queryset.queryset_iterator(
            models.ContentType.objects.all(), 5, gc_collect=True
        )
    )

    # 12 rows / chunksize 5 -> chunks of 5, 5, 2, then one empty
    # chunk to detect exhaustion -> gc.collect() runs after each of
    # the 3 non-empty chunks, not after the exhaustion check.
    assert calls == 3


@pytest.mark.django_db()
def test_gc_collect_defaults_to_false(monkeypatch):
    """Without ``gc_collect=True``, ``gc.collect()`` is never called."""
    _make_content_types(12)
    calls = 0

    def fake_collect() -> int:
        nonlocal calls
        calls += 1
        return 0

    monkeypatch.setattr(queryset.gc, 'collect', fake_collect)

    from django.contrib.contenttypes import models

    list(queryset.queryset_iterator(models.ContentType.objects.all(), 5))

    assert calls == 0
