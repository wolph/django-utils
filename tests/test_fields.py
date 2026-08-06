from django.db import models
from django_utils import fields


class A(models.Model):
    some_attribute = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        app_label = 'tests'


class B(models.Model):
    some_attribute = models.CharField(max_length=100, blank=True, null=True)
    parent = models.ForeignKey(A, on_delete=models.CASCADE)

    # By default the fieldname is assumed to be `get_<field_name>`
    get_some_attribute = fields.RecursiveField()

    # Custom naming is also possible
    some_attribute_with_other_name = fields.RecursiveField('some_attribute')

    # And defaults, in the case of None
    get_some_attribute_with_defaults = fields.RecursiveField(
        field_name='some_attribute', default='some default value'
    )

    class Meta:
        app_label = 'tests'


class C(models.Model):
    level = models.IntegerField(blank=True, null=True)
    parent = models.ForeignKey(
        'tests.C', on_delete=models.CASCADE, blank=True, null=True
    )

    get_level = fields.RecursiveField()

    class Meta:
        app_label = 'tests'


def test_recursive_field():
    a = A(some_attribute='a')
    b = B(some_attribute='b', parent=a)
    c = B(parent=a)

    assert b.get_some_attribute() == 'b'
    assert b.some_attribute_with_other_name() == 'b'
    assert b.get_some_attribute_with_defaults() == 'b'
    assert c.get_some_attribute() == 'a'
    assert c.some_attribute_with_other_name() == 'a'
    assert c.get_some_attribute_with_defaults() == 'a'

    d = A()
    e = B(parent=d)
    assert e.get_some_attribute() is None
    assert e.some_attribute_with_other_name() is None
    assert e.get_some_attribute_with_defaults() == 'some default value'


def test_recursive_field_keeps_falsy_string():
    a = A(some_attribute='parent value')
    b = B(some_attribute='', parent=a)
    assert b.get_some_attribute() == '', (
        "'' was treated as unset and inherited from the parent"
    )


def test_recursive_field_keeps_zero():
    parent = C(level=5)
    child = C(level=0, parent=parent)
    assert child.get_level() == 0, (
        '0 was treated as unset and inherited from the parent'
    )
