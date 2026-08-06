import typing

from django.db import models
from django_utils import base_models, choices, crypto_fields, pg_enum


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
    comment = models.CharField(max_length=50, default='')

    class Meta:
        constraints: typing.ClassVar = [
            models.UniqueConstraint(
                fields=['sandwich', 'rating'], name='uniq_sandwich_rating'
            ),
        ]


class Topping(models.Model):
    sandwich = models.ForeignKey(Sandwich, on_delete=models.CASCADE)
    price = models.IntegerField()
    order = models.IntegerField(default=0)


class Ingredient(models.Model):
    name = models.CharField(max_length=50, unique=True)
    stock = models.IntegerField(default=0)


class Tag(models.Model):
    name = models.CharField(max_length=50)
    sandwiches = models.ManyToManyField(Sandwich, related_name='tags')


class OrderStatus(choices.Choices):
    """Small Choices class exercising django_utils.pg_enum.EnumField."""

    Pending = choices.Choice('pending', 'Pending')
    Shipped = choices.Choice('shipped', 'Shipped')
    Delivered = choices.Choice('delivered', 'Delivered')


class Order(models.Model):
    """EnumField-bearing model.

    ``managed = False``: on PostgreSQL, ``EnumField``'s column type is
    the ``order_status`` enum type, which must already exist before a
    table referencing it can be created -- exactly what the hand-written
    ``CreateEnumType`` migration operation is for (see
    ``django_utils.pg_enum``). ``tests/test_app`` has no migrations
    directory (every other model here auto-syncs), and syncdb has no
    hook to run a hand-written operation before creating a table, so
    letting this model auto-sync would try to create its column against
    a type that doesn't exist yet on every PostgreSQL test run. Tests
    that need this table create/drop it themselves, in the right order,
    via ``connection.schema_editor()``.
    """

    status = pg_enum.EnumField(OrderStatus, default=OrderStatus.Pending)

    class Meta:
        managed = False


if crypto_fields._fernet_available:
    # Guarded: environments that load these settings without the
    # `crypto` extra installed (e.g. the `docs` tox env, which only
    # installs `.[docs]`) must still be able to import this module --
    # instantiating an encrypted field without `cryptography` is
    # exactly what raises ImproperlyConfigured (see test_crypto_fields.py).

    class Secret(models.Model):
        """One field of each django_utils.crypto_fields type."""

        char_value = crypto_fields.EncryptedCharField(max_length=100)
        text_value = crypto_fields.EncryptedTextField()
        json_value = crypto_fields.EncryptedJSONField(null=True, blank=True)
