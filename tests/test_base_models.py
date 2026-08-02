import pytest
from django_utils import base_models


class FakeQuerySet:
    """Stands in for a Django QuerySet: nothing is ever "taken"."""

    def filter(self, **kwargs):
        return self

    def exclude(self, **kwargs):
        return self

    def exists(self):
        return False


class SaveableClass:
    # Mimics an unsaved model instance for SlugMixin.get_unique_slug,
    # which needs both a manager to query against and a pk to exclude.
    pk = None
    _base_manager = FakeQuerySet()

    def save(self):
        pass


class SluggedClass(base_models.SlugMixin, SaveableClass):
    pass


def test_slug_mixin():
    instance = SluggedClass()
    instance.slug = None
    instance.name = 'named'
    instance.save()

    instance = SluggedClass()
    instance.slug = 'slugged'
    instance.name = 'named'
    instance.save()


class ModelBaseTest(base_models.ModelBase):
    class Meta:
        app_label = 'tests'


class ModelBaseProxyTest(ModelBaseTest):
    class Meta:
        proxy = True
        app_label = 'tests'


@pytest.mark.django_db()
def test_slug_collisions_get_a_numeric_suffix():
    from tests.test_app import models

    first = models.Spam.objects.create(name='My Thing', a='x')
    second = models.Spam.objects.create(name='My Thing', a='y')
    third = models.Spam.objects.create(name='My Thing', a='z')

    assert first.slug == 'my-thing'
    assert second.slug == 'my-thing-2'
    assert third.slug == 'my-thing-3'


@pytest.mark.django_db()
def test_explicit_slug_is_never_overwritten():
    from tests.test_app import models

    obj = models.Spam.objects.create(name='My Thing', slug='chosen', a='x')
    assert obj.slug == 'chosen'


@pytest.mark.django_db()
def test_resaving_does_not_collide_with_itself():
    from tests.test_app import models

    obj = models.Spam.objects.create(name='My Thing', a='x')
    original_slug = obj.slug

    obj.slug = ''
    obj.save()

    assert obj.slug == original_slug


@pytest.mark.django_db()
def test_slug_max_attempts_exhausted_raises():
    from tests.test_app import models

    models.LowMaxAttemptsSpam.objects.create(name='My Thing')

    with pytest.raises(ValueError, match='Could not find a free slug'):
        models.LowMaxAttemptsSpam.objects.create(name='My Thing')


@pytest.mark.django_db()
def test_get_unique_slug_probes_with_base_manager_not_filtered_default():
    """A filtered default manager (soft-delete style) must not hide
    existing rows from the uniqueness probe.

    ``SoftDeleteSpam.objects`` (the default manager) filters out rows
    flagged ``is_deleted``, so probing with ``_default_manager`` would
    miss the first row below once it's flagged deleted, and the second
    row would silently collide onto the same slug. Probing with
    ``_base_manager`` -- Django's documented unfiltered manager -- still
    sees it.
    """
    from tests.test_app import models

    first = models.SoftDeleteSpam.objects.create(name='My Thing')
    models.SoftDeleteSpam.objects.filter(pk=first.pk).update(is_deleted=True)

    # Hidden from `objects` (the default manager) now, but still a row
    # in the table with slug 'my-thing'.
    assert not models.SoftDeleteSpam.objects.filter(pk=first.pk).exists()

    second = models.SoftDeleteSpam.objects.create(name='My Thing')

    assert first.slug == 'my-thing'
    assert second.slug == 'my-thing-2'
