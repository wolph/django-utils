from django.db import models
from django_utils import choices

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    from django.utils.translation import ugettext_lazy as _


class TranslatedHuman(models.Model):

    class Gender(choices.Choices):
        Male = choices.Choice('m', _('Male'))
        Female = choices.Choice('f', _('Female'))
        Other = choices.Choice('o', _('Other'))

    gender = models.CharField(max_length=1, choices=Gender.choices)

    class Meta:
        app_label = 'tests'


class Human(models.Model):

    class Gender(choices.Choices):
        Male = choices.Choice('m')
        Female = choices.Choice('f')
        Other = choices.Choice('o')

    gender = models.CharField(max_length=1, choices=Gender.choices)

    class Meta:
        app_label = 'tests'


class SomeModel(models.Model):

    class Enum(choices.Choices):
        Foo = choices.Choice()
        Bar = choices.Choice()
        Spam = choices.Choice()
        Eggs = choices.Choice()

    enum = models.IntegerField(
        choices=Enum.choices, default=Enum.Foo)

    class Meta:
        app_label = 'tests'


def test_named_choices():
    Human(gender=Human.Gender.Male)


def test_unnamed_choices():
    SomeModel(enum=SomeModel.Enum.Spam)


def test_choices():
    repr(Human.Gender)
    str(Human.Gender)


def test_choice():
    repr(Human.Gender.Male)
    str(Human.Gender.Male)


def test_choice_equals():
    choice_a = choices.Choice(value=123, label='123')
    choice_b = choices.Choice(value=123)
    choice_c = choices.Choice(value=456, label='123')

    assert not (choice_a == 'test')
    assert choice_a == 123
    assert not choice_a == 456
    assert choice_a == choice_a
    assert choice_a == choice_b
    assert choice_a != choice_c
    assert hash(choice_a) != hash(choice_c)
    assert hash(choice_a) == hash(choice_b)


def test_choice_deconstruct():
    choices.Choice().deconstruct()
    choices.Choice(value=123).deconstruct()
    choices.Choice(value=123, label='123').deconstruct()
