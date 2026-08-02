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
    _default_manager = FakeQuerySet()

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
