from django.db import models
from django.db.models import base
from django.template import defaultfilters
from python_utils import formatters


class ModelBaseMeta(base.ModelBase):

    '''
    Model base with more readable naming convention

    Example:
    Assuming the model is called `app.FooBarObject`

    Default Django table name: `app_foobarobject`
    Table name with this base: `app_foo_bar_object`
    '''

    def __new__(cls, name, bases, attrs):
        module = attrs['__module__']

        # Get or create Meta
        if 'Meta' in attrs:
            Meta = attrs['Meta']
        else:
            Meta = type(
                'Meta', (object,), dict(
                    __module__=module,
                )
            )
            attrs['Meta'] = Meta

        # Override table name only if not explicitly defined
        if not hasattr(Meta, 'db_table'):  # pragma: no cover
            module_name = formatters.camel_to_underscore(name)
            app_label = module.split('.')[-2]
            Meta.db_table = f'{app_label}_{module_name}'

        return base.ModelBase.__new__(cls, name, bases, attrs)


class ModelBase(models.Model, metaclass=ModelBaseMeta):
    class Meta:
        abstract = True


class CreatedAtModelBase(ModelBase):
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True


class NameMixin(object):

    '''Mixin to automatically get a unicode and repr string base on the name

    >>> x = NameMixin()
    >>> x.pk = 123
    >>> x.name = 'test'
    >>> repr(x)
    '<NameMixin[123]: test>'
    >>> str(x)
    'test'
    >>> str(str(x))
    'test'

    '''

    def __unicode__(self):
        return self.name

    def __str__(self):
        return self.__unicode__()

    def __repr__(self):
        return f'<{self.__class__.__name__}[{self.pk or -1:d}]: {self.name}>'


class SlugMixin(NameMixin):

    '''Mixin to automatically slugify the name and add both a name and slug to
    the model

    >>> x = NameMixin()
    >>> x.pk = 123
    >>> x.name = 'test'
    >>> repr(x)
    '<NameMixin[123]: test>'
    >>> str(x)
    'test'
    >>> str(str(x))
    'test'

    '''

    def save(self, *args, **kwargs):
        if not self.slug and self.name:
            self.slug = defaultfilters.slugify(self.name)

        super(NameMixin, self).save(*args, **kwargs)

    class Meta(object):
        unique_together = ('slug',)


class NameModelBase(NameMixin, ModelBase):
    name = models.CharField(max_length=100)

    class Meta:
        abstract = True


class SlugModelBase(SlugMixin, NameModelBase):
    slug = models.SlugField(max_length=50)

    class Meta:
        abstract = True


class NameCreatedAtModelBase(NameModelBase, CreatedAtModelBase):

    class Meta:
        abstract = True


class SlugCreatedAtModelBase(SlugModelBase, CreatedAtModelBase):

    class Meta:
        abstract = True
