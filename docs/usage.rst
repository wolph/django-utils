Usage
=====

Django Utils is a collection of small Django helper functions, utilities and
classes which make common patterns shorter and easier.

Installation
------------

Install with pip::

    pip install django-utils2

Add ``django_utils`` to your ``INSTALLED_APPS``.

Admin Select / Dropdown / Autocomplete (JSON) Filters
------------------------------------------------------

All of the standard admin list filters are available through
``django_utils.admin.filters`` as:

- The original filter (e.g. ``SimpleListFilter``)
- A basic select/dropdown filter: ``SimpleListFilterDropdown``
- A select2 based autocompleting dropdown filter: ``SimpleListFilterSelect2``

On PostgreSQL you can additionally filter on JSON fields as well given
paths::

    class SomeModelAdmin(admin.ModelAdmin):
        list_filter = (
            JSONFieldFilterSelect2.create('some_json_field__some__sub_path'),
        )

Choices usage
-------------

Django 3.0+ ships native ``models.TextChoices`` / ``models.IntegerChoices``
enums; ``django_utils.choices`` remains for the extra ``Choice`` metadata and
dict-like access it provides::

    from django_utils import choices


    class Human(models.Model):
        class Gender(choices.Choices):
            MALE = 'm'
            FEMALE = 'f'
            OTHER = 'o'

        gender = models.CharField(max_length=1, choices=Gender)

See the `project README
<https://github.com/WoLpH/django-utils/blob/master/README.md>`_ for the
full usage guide.
