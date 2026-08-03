"""Tests for django_utils.admin.export (ExportMixin: CSV/JSON export)."""

import csv
import io
import json

import pytest
from django import http
from django.contrib import admin
from django.contrib.admin import helpers
from django.contrib.auth.models import User
from django_utils.admin import export

from tests.test_app import models

pytestmark = pytest.mark.django_db


class IngredientExportAdmin(export.ExportMixin, admin.ModelAdmin):
    list_display = ('name', 'stock')
    search_fields = ('name',)


class RestrictedIngredientExportAdmin(export.ExportMixin, admin.ModelAdmin):
    export_fields = ('name',)


class SpamExportAdmin(export.ExportMixin, admin.ModelAdmin):
    pass


@pytest.fixture
def model_admin():
    return IngredientExportAdmin(models.Ingredient, admin.AdminSite())


@pytest.fixture
def superuser_request(rf):
    request = rf.post('/admin/test_app/ingredient/')
    request.user = User(is_superuser=True, is_staff=True, is_active=True)
    return request


def _csv_rows(content):
    return list(csv.reader(io.StringIO(content)))


# -- _guard_csv / _export_fields (helper units) ------------------------


@pytest.mark.parametrize('prefix', ['=', '+', '-', '@'])
def test_guard_csv_prefixes_dangerous_strings(prefix):
    value = f'{prefix}SUM(A1:A9)'
    assert export._guard_csv(value) == f"'{value}"


def test_guard_csv_leaves_safe_strings_untouched():
    assert export._guard_csv('safe') == 'safe'


def test_guard_csv_leaves_non_str_values_untouched():
    assert export._guard_csv(42) == 42


def test_export_fields_defaults_to_concrete_field_attnames(model_admin):
    assert export._export_fields(model_admin) == ('id', 'name', 'stock')


def test_export_fields_honours_custom_attribute():
    restricted = RestrictedIngredientExportAdmin(
        models.Ingredient, admin.AdminSite()
    )
    assert export._export_fields(restricted) == ('name',)


# -- CSV ------------------------------------------------------------


def test_export_as_csv_streams_header_and_rows(model_admin, rf):
    salt = models.Ingredient.objects.create(name='salt', stock=3)
    pepper = models.Ingredient.objects.create(name='pepper', stock=7)
    request = rf.post('/admin/test_app/ingredient/')

    response = model_admin.export_as_csv(
        request, models.Ingredient.objects.all()
    )

    assert isinstance(response, http.StreamingHttpResponse)
    assert response['Content-Type'] == 'text/csv; charset=utf-8'
    assert response['Content-Disposition'] == (
        'attachment; filename="ingredient_export.csv"'
    )
    content = b''.join(response.streaming_content).decode()
    rows = _csv_rows(content)
    assert rows[0] == ['id', 'name', 'stock']
    assert rows[1] == [str(salt.pk), 'salt', '3']
    assert rows[2] == [str(pepper.pk), 'pepper', '7']


@pytest.mark.parametrize('prefix', ['=', '+', '-', '@'])
def test_export_as_csv_guards_formula_injection(model_admin, rf, prefix):
    dangerous_name = f'{prefix}SUM(A1:A9)'
    models.Ingredient.objects.create(name=dangerous_name, stock=42)
    request = rf.post('/admin/test_app/ingredient/')

    response = model_admin.export_as_csv(
        request, models.Ingredient.objects.all()
    )

    data_row = _csv_rows(b''.join(response.streaming_content).decode())[1]
    assert data_row[1] == f"'{dangerous_name}"
    # A numeric column is never guarded, even on a row that also
    # carries a guarded string value.
    assert data_row[2] == '42'


def test_export_fields_restricts_csv_columns(rf):
    restricted = RestrictedIngredientExportAdmin(
        models.Ingredient, admin.AdminSite()
    )
    models.Ingredient.objects.create(name='salt', stock=3)
    request = rf.post('/admin/test_app/ingredient/')

    response = restricted.export_as_csv(
        request, models.Ingredient.objects.all()
    )

    rows = _csv_rows(b''.join(response.streaming_content).decode())
    assert rows[0] == ['name']
    assert rows[1] == ['salt']


# -- JSON -----------------------------------------------------------


def test_export_as_json_parses_and_matches_rows(model_admin, rf):
    salt = models.Ingredient.objects.create(name='salt', stock=3)
    request = rf.post('/admin/test_app/ingredient/')

    response = model_admin.export_as_json(
        request, models.Ingredient.objects.all()
    )

    assert isinstance(response, http.StreamingHttpResponse)
    assert response['Content-Type'] == 'application/json; charset=utf-8'
    assert response['Content-Disposition'] == (
        'attachment; filename="ingredient_export.json"'
    )
    content = b''.join(response.streaming_content).decode()
    assert json.loads(content) == [{'id': salt.pk, 'name': 'salt', 'stock': 3}]


def test_export_as_json_serializes_non_native_values_via_str(rf):
    spam_admin = SpamExportAdmin(models.Spam, admin.AdminSite())
    models.Spam.objects.create(name='cheese', a='yes')
    spam = models.Spam.objects.get(name='cheese')
    request = rf.post('/admin/test_app/spam/')

    response = spam_admin.export_as_json(request, models.Spam.objects.all())

    content = b''.join(response.streaming_content).decode()
    row = json.loads(content)[0]
    # DateTimeField values are not JSON-native; ``default=str`` in
    # json.dumps() is what makes them serializable at all.
    assert row['created_at'] == str(spam.created_at)
    assert row['updated_at'] == str(spam.updated_at)


# -- Streaming sanity (many rows via queryset_iterator chunking) ----


@pytest.mark.parametrize(
    ('action_name', 'row_count'),
    [
        ('export_as_csv', lambda content: len(_csv_rows(content)) - 1),
        ('export_as_json', lambda content: len(json.loads(content))),
    ],
    ids=['csv', 'json'],
)
def test_streaming_handles_many_rows_across_chunks(
    model_admin, rf, monkeypatch, action_name, row_count
):
    # A small chunk size forces queryset_iterator to issue several
    # keyset-paginated queries instead of one, exercising the actual
    # chunk boundary rather than a single-chunk happy path.
    monkeypatch.setattr(export, '_CHUNK_SIZE', 47)
    models.Ingredient.objects.bulk_create(
        models.Ingredient(name=f'item-{i}', stock=i) for i in range(250)
    )
    request = rf.post('/admin/test_app/ingredient/')
    action = getattr(model_admin, action_name)

    response = action(request, models.Ingredient.objects.all())

    content = b''.join(response.streaming_content).decode()
    assert row_count(content) == 250


def test_export_as_csv_guard_survives_csv_quoting(model_admin, rf):
    """A guarded value that ALSO contains the delimiter: the ' prefix is
    applied first, then csv.writer quotes the whole cell — parsing it
    back must yield the prefixed original, not a mangled split."""
    models.Ingredient.objects.create(name='=1,2', stock=1)
    request = rf.post('/admin/test_app/ingredient/')

    response = model_admin.export_as_csv(
        request, models.Ingredient.objects.all()
    )

    data_row = _csv_rows(b''.join(response.streaming_content).decode())[1]
    assert data_row[1] == "'=1,2"


def test_export_as_json_zero_rows_is_valid_empty_array(model_admin, rf):
    request = rf.post('/admin/test_app/ingredient/')
    response = model_admin.export_as_json(
        request, models.Ingredient.objects.none()
    )
    content = b''.join(response.streaming_content).decode()
    assert json.loads(content) == []


def test_export_fk_columns_use_attname(rf):
    """FKs export as their raw <name>_id column value, per the
    attname-based default field list."""
    sandwich = models.Sandwich.objects.create(data={})
    models.Review.objects.create(sandwich=sandwich, rating=4)

    class ReviewExportAdmin(export.ExportMixin, admin.ModelAdmin):
        pass

    model_admin = ReviewExportAdmin(models.Review, admin.AdminSite())
    request = rf.post('/admin/test_app/review/')
    response = model_admin.export_as_csv(request, models.Review.objects.all())
    rows = _csv_rows(b''.join(response.streaming_content).decode())
    assert 'sandwich_id' in rows[0]
    sandwich_column = rows[0].index('sandwich_id')
    assert rows[1][sandwich_column] == str(sandwich.pk)


# -- get_actions() ----------------------------------------------------


def test_both_export_actions_registered(model_admin, superuser_request):
    actions = model_admin.get_actions(superuser_request)
    assert 'export_as_csv' in actions
    assert 'export_as_json' in actions


# -- Real changelist POST (admin machinery end to end) ----------------


def test_changelist_action_post_streams_csv_response(admin_client):
    salt = models.Ingredient.objects.create(name='salt', stock=3)

    response = admin_client.post(
        '/admin/test_app/ingredient/',
        data={
            'action': 'export_as_csv',
            helpers.ACTION_CHECKBOX_NAME: [str(salt.pk)],
            'index': '0',
        },
    )

    assert response.status_code == 200
    assert response['Content-Type'] == 'text/csv; charset=utf-8'
    assert response['Content-Disposition'] == (
        'attachment; filename="ingredient_export.csv"'
    )
    content = b''.join(response.streaming_content).decode()
    rows = _csv_rows(content)
    assert rows[0] == ['id', 'name', 'stock']
    assert rows[1] == [str(salt.pk), 'salt', '3']
