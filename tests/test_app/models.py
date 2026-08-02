from django.db import models
from django_utils import base_models


class Spam(base_models.SlugCreatedAtModelBase):
    a = models.CharField(max_length=50)


class LowMaxAttemptsSpam(base_models.SlugCreatedAtModelBase):
    """Exercises SlugMixin.get_unique_slug's exhaustion branch."""

    slugify_max_attempts = 1


class Eggs(Spam):
    b = models.CharField(max_length=100)


class RecursionTest(models.Model):
    parent = models.ForeignKey(Spam, on_delete=models.CASCADE)


class Sandwich(models.Model):
    data = models.JSONField(default=dict)
