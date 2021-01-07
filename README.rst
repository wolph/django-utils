Introduction
============

Travis status:

.. image:: https://travis-ci.org/WoLpH/django-utils.png?branch=master
  :target: https://travis-ci.org/WoLpH/django-utils

Coverage:

.. image:: https://coveralls.io/repos/WoLpH/django-utils/badge.png?branch=master
  :target: https://coveralls.io/r/WoLpH/django-utils?branch=master

Django Utils is a collection of small Django helper functions, utilities and
classes which make common patterns shorter and easier. It is by no means a
complete collection but it has served me quite a bit in the past and I will
keep extending it.

Examples are:

 - Enum based choicefields
 - Models with automatic `__str__`, `__unicode__` and `__repr__` functions
   based on names and/or slugs using simple mixins.
 - Models with automatic `updated_at` and `created_at` fields
 - Models with automatic slugs based on the `name` property.
 - Iterating through querysets in predefined chunks to prevent out of memory
   errors

The library depends on the Python Utils library.

Documentation is available at: http://django-utils-2.readthedocs.io/en/latest/

Install
-------

To install:

 1. Run `pip install django-utils2` or execute `python setup.py install` in the source directory
 2. Add `django_utils` to your `INSTALLED_APPS`
 
If you want to run the tests, run `py.test` (requirements in `tests/requirements.txt`)


Usage
-----

To enable easy to use choices which are more convenient than the Django 3.0 choices system you can use this:

.. code-block:: python

    from django_utils import choices


    # For manually specifying the value (automatically detects `str`, `int` and `float`):
    class Human(models.Model):
        class Gender(choices.Choices):
            MALE = 'm'
            FEMALE = 'f'
            OTHER = 'o'

        gender = models.CharField(max_length=1, choices=Gender)


    # To define the values as `male` implicitly:
    class Human(models.Model):
        class Gender(choices.Choices):
            MALE = choices.Choice()
            FEMALE = choices.Choice()
            OTHER = choices.Choice()

        gender = models.CharField(max_length=1, choices=Gender)


    # Or explicitly define them
    class Human(models.Model):
        class Gender(choices.Choices):
            MALE = choices.Choice('m', 'male')
            FEMALE = choices.Choice('f', 'female')
            OTHER = choices.Choice('o', 'other')

        gender = models.CharField(max_length=1, choices=Gender)

A PostgreSQL ENUM field will be coming soon to automatically facilitate the creation of the enum if needed.

Links
-----

* Documentation
    - http://django-utils-2.readthedocs.org/en/latest/
* Source
    - https://github.com/WoLpH/django-utils
* Bug reports 
    - https://github.com/WoLpH/django-utils/issues
* Package homepage
    - https://pypi.python.org/pypi/django-utils2
* My blog
    - http://w.wol.ph/

