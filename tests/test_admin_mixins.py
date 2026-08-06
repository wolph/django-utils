"""Tests for django_utils.admin.mixins.ReadOnlyModelAdminMixin."""

import csv
import io

import pytest
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.models import User
from django_utils.admin import export, mixins

from tests.test_app import models

pytestmark = pytest.mark.django_db


class ReadOnlyIngredientAdmin(
    mixins.ReadOnlyModelAdminMixin, admin.ModelAdmin
):
    list_display = ('name', 'stock')
    search_fields = ('name',)


class ReadOnlyTagAdmin(mixins.ReadOnlyModelAdminMixin, admin.ModelAdmin):
    pass


class ReadOnlyShoutingIngredientAdmin(
    mixins.ReadOnlyModelAdminMixin, admin.ModelAdmin
):
    """The ordinary `fields` + `readonly_fields` + method pattern --
    fine on a plain `ModelAdmin` -- regression-tests that the mixin
    merges with, rather than replaces, an admin's own declared
    `readonly_fields`."""

    fields = ('name', 'stock', 'shouting_name')
    readonly_fields = ('shouting_name',)

    def shouting_name(self, obj):
        return obj.name.upper()

    shouting_name.short_description = 'SHOUTING NAME'


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


class ReadOnlyExportIngredientAdmin(
    mixins.ReadOnlyModelAdminMixin, export.ExportMixin, admin.ModelAdmin
):
    """Read-only + export: a common 'view and download, never edit'
    dashboard admin. `ReadOnlyModelAdminMixin` first in the base list
    denies add/change/delete; `ExportMixin`'s actions still register
    and still work (neither mixin declares `get_actions`/`actions` in
    a way that shadows the other -- `ReadOnlyModelAdminMixin` has no
    `actions` attribute at all, so MRO attribute lookup finds
    `ExportMixin.actions`)."""

    list_display = ('name', 'stock')


class ReadOnlyCountSandwichAdmin(
    mixins.ReadOnlyModelAdminMixin, mixins.CountColumnMixin, admin.ModelAdmin
):
    """Read-only + count columns: browsing-only dashboard with sortable
    related-object counts. Neither mixin overrides a method the other
    depends on, so both apply independently."""

    list_display = ('id',)
    count_columns = ('review', 'topping')


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


def test_change_view_includes_declared_readonly_fields(rf):
    """Regression: ``get_readonly_fields()`` used to REPLACE the wrapped
    admin's own ``readonly_fields`` outright instead of merging with it.

    ``fields = (..., 'shouting_name')`` + ``readonly_fields =
    ('shouting_name',)`` + a ``shouting_name()`` method is the ordinary
    way to add a computed read-only display field -- fine on a plain
    ``ModelAdmin`` with no mixin at all. Replacing ``readonly_fields``
    outright dropped ``shouting_name`` from both ``form.base_fields``
    (excluded because ``get_form()`` consults the same, now-replaced,
    ``get_readonly_fields()``) and the returned ``readonly_fields``
    (recomputed here from concrete/M2M model fields only -- a
    method-backed display attribute is neither): present in the
    fieldset, absent from both collections -- the same ``KeyError``
    crash class as ``test_change_view_includes_m2m_in_readonly`` above.
    Replicate that exact fieldset iteration here for the same reason
    that test does: asserting on ``get_form()`` alone would pass even
    against the buggy (replacing) implementation.
    """
    ingredient = models.Ingredient.objects.create(name='salt', stock=3)
    model_admin = ReadOnlyShoutingIngredientAdmin(
        models.Ingredient, admin.AdminSite()
    )
    request = rf.get(f'/admin/test_app/ingredient/{ingredient.pk}/change/')
    request.user = User.objects.create(
        username='shouting-admin',
        is_superuser=True,
        is_staff=True,
        is_active=True,
    )

    readonly = model_admin.get_readonly_fields(request, ingredient)
    assert 'shouting_name' in readonly

    form_class = model_admin.get_form(request, ingredient, change=True)
    admin_form = helpers.AdminForm(
        form_class(instance=ingredient),
        list(model_admin.get_fieldsets(request, ingredient)),
        {},
        readonly,
        model_admin=model_admin,
    )
    rendered: list[str] = []
    for fieldset in admin_form:
        for line in fieldset:  # pre-fix: KeyError 'shouting_name' here
            rendered.extend(
                str(field.contents())
                for field in line
                if isinstance(field, helpers.AdminReadonlyField)
            )
    # The computed field's readonly contents must have rendered, and it
    # must appear in the iterated fieldlines -- completing the iteration
    # at all is the crash-regression proof.
    assert any('SALT' in value for value in rendered)
    assert 'shouting_name' in {
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


def test_predefined_admin_keeps_annotation_alongside_custom_method(
    predefined_count_admin, superuser_request, sandwich_with_relations
):
    """A user-overridden review_count display method wins the display
    slot while the queryset annotation still exists for ordering — the
    annotation lives on model rows, the method on the admin instance;
    different namespaces, no collision."""
    row = predefined_count_admin.get_queryset(superuser_request).get(
        pk=sandwich_with_relations.pk
    )
    assert row.review_count == 2
    assert predefined_count_admin.review_count(row) == 'custom'


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


# -- Composition with the other admin mixins ---------------------------


def test_readonly_composes_with_export_mixin(superuser_request):
    """Read-only + export: view-and-download-only dashboards. Export
    actions register, `delete_selected` doesn't, and the action itself
    still streams real data -- not just markup/attribute assertions."""
    salt = models.Ingredient.objects.create(name='salt', stock=3)
    model_admin = ReadOnlyExportIngredientAdmin(
        models.Ingredient, admin.AdminSite()
    )

    actions = model_admin.get_actions(superuser_request)
    assert 'export_as_csv' in actions
    assert 'export_as_json' in actions
    assert 'delete_selected' not in actions

    response = model_admin.export_as_csv(
        superuser_request, models.Ingredient.objects.all()
    )
    assert response.status_code == 200
    content = b''.join(response.streaming_content).decode()
    rows = list(csv.reader(io.StringIO(content)))
    assert rows[0] == ['id', 'name', 'stock']
    assert rows[1] == [str(salt.pk), 'salt', '3']


def test_readonly_composes_with_count_column_mixin(
    superuser_request, sandwich_with_relations
):
    """Read-only + count columns: browsing-only dashboard with sortable
    related-object counts, neither mixin stepping on the other."""
    model_admin = ReadOnlyCountSandwichAdmin(
        models.Sandwich, admin.AdminSite()
    )
    assert model_admin.check() == []

    queryset = model_admin.get_queryset(superuser_request)
    assert {'review_count', 'topping_count'} <= set(queryset.query.annotations)
    row = queryset.get(pk=sandwich_with_relations.pk)
    assert (row.review_count, row.topping_count) == (2, 3)

    display = model_admin.get_list_display(superuser_request)
    assert 'review_count' in display
    assert 'topping_count' in display
