# vim: set fileencoding=utf-8 :
from django.contrib import admin

from django_utils.admin import filters

from . import models


class SpamAdmin(admin.ModelAdmin):

    list_display = ('id', 'updated_at', 'created_at', 'name', 'slug', 'a')
    list_filter = (
        'updated_at',
        'created_at',
        ('slug', filters.AllValuesFieldListFilterDropdown),
    )
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ['name']}
    date_hierarchy = 'created_at'


class EggsAdmin(admin.ModelAdmin):

    list_display = (
        'updated_at',
        'created_at',
        'slug',
    )
    list_filter = (
        'updated_at',
        'created_at',
        ('slug', filters.AllValuesFieldListFilterSelect2),
    )
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ['name']}
    date_hierarchy = 'created_at'


class RecursionTestAdmin(admin.ModelAdmin):

    list_display = ('id', 'parent')
    list_filter = (
        ('parent', filters.RelatedFieldListFilterSelect2),
    )


def _register(model, admin_class):
    admin.site.register(model, admin_class)


_register(models.Spam, SpamAdmin)
_register(models.Eggs, EggsAdmin)
_register(models.RecursionTest, RecursionTestAdmin)
