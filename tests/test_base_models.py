from django_utils import base_models


class SaveableClass(object):
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
    pass


class ModelBaseProxyTest(ModelBaseTest):
    class Meta:
        proxy = True

