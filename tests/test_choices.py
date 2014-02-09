from django.db import models
from django_utils import choices
from django.utils.translation import ugettext_lazy as _


class TranslatedHuman(models.Model):
    class Gender(choices.Choices):
        Male = choices.Choice('m', _('Male'))
        Female = choices.Choice('f', _('Female'))
        Other = choices.Choice('o', _('Other'))

    gender = models.CharField(max_length=1, choices=Gender.choices)


class Human(models.Model):
    class Gender(choices.Choices):
        Male = choices.Choice('m')
        Female = choices.Choice('f')
        Other = choices.Choice('o')

    gender = models.CharField(max_length=1, choices=Gender.choices)


class SomeModel(models.Model):
    class Enum(choices.Choices):
        Foo = choices.Choice()
        Bar = choices.Choice()
        Spam = choices.Choice()
        Eggs = choices.Choice()

    enum = models.IntegerField(
        choices=Enum.choices, default=Enum.Foo)


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

