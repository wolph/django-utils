import pytest
from django_utils import queryset


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
