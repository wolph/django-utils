"""Tests for django_utils.admin.mixins.ReadOnlyModelAdminMixin."""

import pytest
from django.contrib import admin
from django.contrib.admin import helpers
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


class CountSandwichAdmin(mixins.CountColumnMixin, admin.ModelAdmin):
    list_display = ('id',)
    count_columns = ('review', 'topping')


class PreDefinedCountSandwichAdmin(mixins.CountColumnMixin, admin.ModelAdmin):
    """Declares its own review_count, already placed in list_display."""

    list_display = ('id', 'review_count')
    count_columns = ('review',)

    def review_count(self, obj):
        return 'custom'

    review_count.short_description = 'custom description'


@pytest.fixture
def model_admin():
    return ReadOnlyIngredientAdmin(models.Ingredient, admin.AdminSite())


@pytest.fixture
def count_admin():
    return CountSandwichAdmin(models.Sandwich, admin.AdminSite())


@pytest.fixture
def predefined_count_admin():
    return PreDefinedCountSandwichAdmin(models.Sandwich, admin.AdminSite())


@pytest.fixture
def superuser_request(rf):
    request = rf.get('/admin/test_app/ingredient/')
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    return request


@pytest.fixture
def sandwich_with_relations():
    sandwich = models.Sandwich.objects.create(data={})
    for rating in (2, 4):
        models.Review.objects.create(sandwich=sandwich, rating=rating)
    for order, price in enumerate((1, 3, 5), 1):
        models.Topping.objects.create(
            sandwich=sandwich, price=price, order=order
        )
    return sandwich


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
    form.base_fields nor readonly_fields.

    The crash lived in template rendering: ``change_form.html`` iterates
    ``helpers.AdminForm`` fieldsets, and building a ``Fieldline`` for a
    field that is in neither collection raises ``KeyError`` -> 500 on a
    plain GET (reachable: ``has_view_or_change_permission`` is an OR and
    view permission stays True). Replicate that exact iteration here —
    asserting on ``get_form()`` alone would pass even against the buggy
    implementation.
    """
    tag = models.Tag.objects.create(name='classic')
    tag.sandwiches.add(models.Sandwich.objects.create(data={}))
    model_admin = ReadOnlyTagAdmin(models.Tag, admin.AdminSite())
    request = rf.get(f'/admin/test_app/tag/{tag.pk}/change/')
    request.user = User.objects.create(
        username='m2m-admin', is_superuser=True, is_staff=True, is_active=True
    )

    readonly = model_admin.get_readonly_fields(request, tag)
    assert 'sandwiches' in readonly

    form_class = model_admin.get_form(request, tag, change=True)
    admin_form = helpers.AdminForm(
        form_class(instance=tag),
        list(model_admin.get_fieldsets(request, tag)),
        {},
        readonly,
        model_admin=model_admin,
    )
    rendered: list[str] = []
    for fieldset in admin_form:
        for line in fieldset:  # pre-fix: KeyError 'sandwiches' here
            rendered.extend(
                str(field.contents())
                for field in line
                if isinstance(field, helpers.AdminReadonlyField)
            )
    # The name field's readonly contents must have rendered, and the
    # M2M field must appear in the iterated fieldlines — completing the
    # iteration at all is the crash-regression proof.
    assert any('classic' in value for value in rendered)
    assert 'sandwiches' in {
        field
        for fieldset in admin_form
        for line in fieldset
        for field in line.fields
    }


def test_view_permission_respects_default_for_non_staff_user(rf):
    """Verify the mixin leaves Django's default view permission logic
    untouched: a non-staff user without explicit permissions gets False."""
    model_admin = ReadOnlyIngredientAdmin(models.Ingredient, admin.AdminSite())
    request = rf.get('/admin/test_app/ingredient/')
    request.user = User.objects.create(is_staff=False, is_active=True)
    assert model_admin.has_view_permission(request) is False


def test_count_columns_annotate_correctly(
    count_admin, superuser_request, sandwich_with_relations
):
    row = count_admin.get_queryset(superuser_request).get(
        pk=sandwich_with_relations.pk
    )
    assert row.review_count == 2
    assert row.topping_count == 3


def test_count_columns_no_fan_out(
    count_admin, superuser_request, sandwich_with_relations
):
    # Two relations on one changelist row: the classic JOIN bug would
    # report 6/6 here.
    row = count_admin.get_queryset(superuser_request).get(
        pk=sandwich_with_relations.pk
    )
    assert (row.review_count, row.topping_count) == (2, 3)


def test_count_columns_appended_to_list_display(
    count_admin, superuser_request
):
    display = count_admin.get_list_display(superuser_request)
    assert display[-2:] == ('review_count', 'topping_count')


def test_count_column_methods_sortable(count_admin):
    method = count_admin.review_count
    assert method.admin_order_field == 'review_count'
    assert method.short_description == 'review count'


def test_count_column_method_returns_annotated_value(
    count_admin, superuser_request, sandwich_with_relations
):
    row = count_admin.get_queryset(superuser_request).get(
        pk=sandwich_with_relations.pk
    )
    assert count_admin.review_count(row) == 2


def test_changelist_orders_by_count(
    count_admin, superuser_request, sandwich_with_relations, rf
):
    zero_review_sandwich = models.Sandwich.objects.create(data={})
    # get_list_display() == ('id', 'review_count', 'topping_count'); 'o'
    # is a 1-indexed position into that tuple, so index 2 sorts by
    # review_count.
    display = count_admin.get_list_display(superuser_request)
    order_index = display.index('review_count') + 1
    assert order_index == 2

    request = rf.get('/admin/test_app/sandwich/', {'o': str(order_index)})
    request.user = superuser_request.user
    changelist = count_admin.get_changelist_instance(request)
    ascending = list(changelist.get_queryset(request))
    # Ascending: 0 reviews (zero_review_sandwich) sorts before 2 reviews.
    assert [row.pk for row in ascending] == [
        zero_review_sandwich.pk,
        sandwich_with_relations.pk,
    ]

    descending_request = rf.get(
        '/admin/test_app/sandwich/', {'o': f'-{order_index}'}
    )
    descending_request.user = superuser_request.user
    descending_changelist = count_admin.get_changelist_instance(
        descending_request
    )
    descending = list(descending_changelist.get_queryset(descending_request))
    assert [row.pk for row in descending] == [
        sandwich_with_relations.pk,
        zero_review_sandwich.pk,
    ]


def test_count_column_skips_existing_attribute(predefined_count_admin):
    # The admin already defines review_count itself; the mixin must not
    # clobber it with a generated method.
    assert predefined_count_admin.review_count.short_description == (
        'custom description'
    )


def test_count_column_not_duplicated_in_list_display(
    predefined_count_admin, superuser_request
):
    display = predefined_count_admin.get_list_display(superuser_request)
    assert display == ('id', 'review_count')


def test_count_admin_checks_pass(count_admin):
    assert count_admin.check() == []
