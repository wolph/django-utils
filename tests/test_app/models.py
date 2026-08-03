from django.db import models
from django_utils import base_models


class Spam(base_models.SlugCreatedAtModelBase):
    a = models.CharField(max_length=50)


class LowMaxAttemptsSpam(base_models.SlugCreatedAtModelBase):
    """Exercises SlugMixin.get_unique_slug's exhaustion branch."""

    slugify_max_attempts = 1


class ActiveManager(models.Manager):
    """Soft-delete-style manager: hides rows flagged ``is_deleted``."""

    def get_queryset(self) -> models.QuerySet['SoftDeleteSpam']:
        return super().get_queryset().filter(is_deleted=False)


class SoftDeleteSpam(base_models.SlugCreatedAtModelBase):
    """Exercises get_unique_slug's uniqueness probe against a model whose
    default manager filters out some rows (soft-delete style).

    ``objects`` is the only manager declared, so it also becomes
    ``_default_manager``; ``_base_manager`` stays Django's plain,
    unfiltered auto-created manager regardless.
    """

    is_deleted = models.BooleanField(default=False)

    objects = ActiveManager()


class Eggs(Spam):
    b = models.CharField(max_length=100)


class RecursionTest(models.Model):
    parent = models.ForeignKey(Spam, on_delete=models.CASCADE)


class Sandwich(models.Model):
    data = models.JSONField(default=dict)


class Review(models.Model):
    sandwich = models.ForeignKey(Sandwich, on_delete=models.CASCADE)
    rating = models.IntegerField()


class Topping(models.Model):
    sandwich = models.ForeignKey(Sandwich, on_delete=models.CASCADE)
    price = models.IntegerField()
