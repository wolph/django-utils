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


class ReadOnlyTagAdmin(mixins.ReadOnlyModelAdminMixin, admin.ModelAdmin):
    pass


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


def test_change_view_includes_m2m_in_readonly(rf):
    """Regression: M2M fields sat in the fieldset but in neither
    form.base_fields nor readonly_fields -> KeyError/500 on render.
    Verify readonly_fields includes M2M fields."""
    tag = models.Tag.objects.create(name='classic')
    tag.sandwiches.add(models.Sandwich.objects.create(data={}))
    model_admin = ReadOnlyTagAdmin(models.Tag, admin.AdminSite())
    request = rf.get(f'/admin/test_app/tag/{tag.pk}/change/')
    request.user = User.objects.create(
        pk=1, is_superuser=True, is_staff=True, is_active=True
    )
    # Verify M2M field is in readonly_fields (the regression fix)
    readonly = model_admin.get_readonly_fields(request, tag)
    assert 'sandwiches' in readonly
    # Verify form generation doesn't crash with M2M in readonly_fields
    form = model_admin.get_form(request, tag, change=True)
    # The form should be generated without KeyError on render
    assert form is not None


def test_view_permission_respects_default_for_non_staff_user(rf):
    """Verify the mixin leaves Django's default view permission logic
    untouched: a non-staff user without explicit permissions gets False."""
    model_admin = ReadOnlyIngredientAdmin(models.Ingredient, admin.AdminSite())
    request = rf.get('/admin/test_app/ingredient/')
    request.user = User.objects.create(is_staff=False, is_active=True)
    assert model_admin.has_view_permission(request) is False
