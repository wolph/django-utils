import functools


class RecursiveField(object):

    PREFIX = 'get_'

    def __init__(self, field_name=None, parent_field='parent', default=None):
        self.field_name = field_name
        self.parent_field = parent_field
        self.default = default

    def contribute_to_class(self, cls, name):
        if not self.field_name:
            assert name.startswith(self.PREFIX)
            self.field_name = name.replace(self.PREFIX, '', 1)

        setattr(cls, name, self)

    def get(self, instance):
        name = self.field_name
        assert name

        value = None
        while instance and not value:
            value = getattr(instance, name, None)
            instance = getattr(instance, self.parent_field, None)

        if value is None:
            value = self.default

        return value

    def __get__(self, instance, owner):
        return functools.partial(self.get, instance)


