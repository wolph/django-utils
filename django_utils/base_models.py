from django.db.models import base
from python_utils import converters


class ModelBase(base.ModelBase):
    '''
    Model base with more readable naming convention

    Example:
    Assuming the model is called `app.FooBarObject`

    Default Django table name: `app_foobarobject`
    Table name with this base: `app_foo_bar_object`
    '''

    def __new__(cls, name, bases, attrs):
        class_ = base.ModelBase.__new__(cls, name, bases, attrs)
        module_name = converters.camel_to_underscore(name)

        app_label = class_.__module__.split('.')[-2]
        db_table = '%s_%s' % (app_label, module_name)
        if not getattr(class_._meta, 'proxy', False):
            class_._meta.db_table = db_table

        return class_

