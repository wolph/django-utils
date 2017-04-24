import six
from django.db.models import base
from django.db import models
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
        class_ = base.ModelBase.__new__(cls, name, bases, attrs)
        module_name = formatters.camel_to_underscore(name)

        app_label = class_.__module__.split('.')[-2]
        db_table = '%s_%s' % (app_label, module_name)
        if not getattr(class_._meta, 'proxy', False):
            class_._meta.db_table = db_table

        return class_


class ModelBase(six.with_metaclass(ModelBaseMeta, models.Model)):
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
    >>> str(six.text_type(x))
    'test'

    '''

    def __unicode__(self):
        return self.name

    def __str__(self):
        out = self.__unicode__()
        if six.PY2:
            out = out.encode('utf-8', 'replace')
        return out

    def __repr__(self):
        repr_ = six.text_type('<%s[%d]: %s>') % (
            self.__class__.__name__,
            self.pk or -1,
            self.name,
        )
        if six.PY2:
            repr_ = repr_.encode('utf-8')
        return repr_


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
    >>> str(six.text_type(x))
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
