"""Tests for django_utils.admin.mixins.ReadOnlyModelAdminMixin."""

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django_utils.admin import mixins

from tests.test_app import models

pytestmark = pytest.mark.django_db


class ReadOnlyIngredientAdmin(
    mixins.ReadOnlyModelAdminMixin, admin.ModelAdmin
):
    list_display = ('name', 'stock')
    search_fields = ('name',)


@pytest.fixture
def model_admin():
    return ReadOnlyIngredientAdmin(models.Ingredient, admin.AdminSite())


@pytest.fixture
def superuser_request(rf):
    request = rf.get('/admin/test_app/ingredient/')
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    return request


def test_add_change_delete_denied_even_for_superuser(
    model_admin, superuser_request
):
    assert model_admin.has_add_permission(superuser_request) is False
    assert model_admin.has_change_permission(superuser_request) is False
    assert model_admin.has_delete_permission(superuser_request) is False


def test_view_permission_untouched(model_admin, superuser_request):
    assert model_admin.has_view_permission(superuser_request) is True


def test_all_concrete_fields_readonly(model_admin, superuser_request):
    readonly = set(model_admin.get_readonly_fields(superuser_request))
    assert {'id', 'name', 'stock'} <= readonly


def test_list_configuration_untouched(model_admin):
    assert model_admin.list_display == ('name', 'stock')
    assert model_admin.search_fields == ('name',)


def test_changelist_renders(model_admin, superuser_request):
    models.Ingredient.objects.create(name='salt', stock=3)
    changelist = model_admin.get_changelist_instance(superuser_request)
    assert changelist.get_queryset(superuser_request).count() == 1


def test_admin_checks_pass(model_admin):
    assert model_admin.check() == []
