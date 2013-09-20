from django_utils import queryset


def test_empty_queryset():
    from django.contrib.auth import models
    for user in queryset.queryset_iterator(models.User.objects.all()):
        pass


def test_full_queryset():
    from django.contrib.contenttypes import models
    for user in queryset.queryset_iterator(models.ContentType.objects.all()):
        pass

