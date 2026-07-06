import datetime

import pytest
from django.contrib import admin
from django.core.cache import cache as django_cache
from django.test import RequestFactory
from django_utils.admin import filters

from tests.test_app import models


@pytest.fixture(autouse=True)
def _clear_cache():
    django_cache.clear()
    yield
    django_cache.clear()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def model_admin():
    return admin.ModelAdmin(models.Sandwich, admin.site)


def make_filter(filter_class, rf, model_admin, params=None):
    request = rf.get('/admin/test_app/sandwich/')
    return (
        filter_class(request, params or {}, models.Sandwich, model_admin),
        request,
    )


def test_create_requires_nested_path():
    with pytest.raises(AssertionError):
        filters.JSONFieldFilter.create('flat_path')


def test_create_defaults():
    filter_class = filters.JSONFieldFilter.create('data__filling')
    assert filter_class.field_path == 'data__filling'
    assert filter_class.parameter_name == 'data__filling'
    assert filter_class.title == 'Data  Filling'
    assert filter_class.timeout is None


@pytest.mark.django_db
def test_attribute_path(rf, model_admin):
    filter_class = filters.JSONFieldFilter.create('data__a__b')
    instance, _request = make_filter(filter_class, rf, model_admin)
    assert instance.attribute_path == 'a__b'
    assert filter_class.field_path == 'data__a__b'


@pytest.mark.django_db
def test_lookups_and_queryset(rf, model_admin):
    models.Sandwich.objects.create(data={'filling': 'cheese'})
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    filter_class = filters.JSONFieldFilter.create('data__filling')
    instance, request = make_filter(filter_class, rf, model_admin)
    lookups = list(instance.lookups(request, model_admin))
    assert ('cheese', 'Cheese') in lookups
    assert ('ham', 'Ham') in lookups

    # Set used_parameters directly: Django's param parsing differs between
    # 4.2 (string passthrough) and 5.x (list, takes value[-1]), so passing
    # the value via params would test version-specific behavior instead of
    # our value() -> cast -> filter code path.
    instance, request = make_filter(filter_class, rf, model_admin)
    instance.used_parameters = {'data__filling': 'ham'}
    queryset = instance.queryset(request, models.Sandwich.objects.all())
    assert queryset.count() == 1

    # No value selected: queryset passes through unfiltered
    instance, request = make_filter(filter_class, rf, model_admin)
    queryset = instance.queryset(request, models.Sandwich.objects.all())
    assert queryset.count() == 3


@pytest.mark.django_db
def test_lookups_are_cached(rf, model_admin):
    models.Sandwich.objects.create(data={'filling': 'cheese'})
    filter_class = filters.JSONFieldFilter.create('data__filling')
    instance, request = make_filter(filter_class, rf, model_admin)
    first = list(instance.lookups(request, model_admin))

    # A second instance must hit the cache, not the database
    models.Sandwich.objects.all().delete()
    instance, request = make_filter(filter_class, rf, model_admin)
    assert list(instance.lookups(request, model_admin)) == first


@pytest.mark.django_db
def test_zero_timeout_disables_cache(rf, model_admin):
    models.Sandwich.objects.create(data={'filling': 'cheese'})
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', timeout=datetime.timedelta(0)
    )
    instance, request = make_filter(filter_class, rf, model_admin)
    assert instance.get_lookups_cache_timeout() == 0.0
    list(instance.lookups(request, model_admin))
    assert instance.get_lookups_cache(request) is None


@pytest.mark.django_db
def test_custom_formatter_is_not_bound(rf, model_admin):
    """A 1-arg formatter must receive only the value (bug B1)."""
    models.Sandwich.objects.create(data={'filling': 'cheese'})
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', formatter=lambda value: f'F:{value}'
    )
    instance, request = make_filter(filter_class, rf, model_admin)
    assert ('cheese', 'F:cheese') in list(
        instance.lookups(request, model_admin)
    )


@pytest.mark.django_db
def test_custom_cast_is_not_bound(rf, model_admin):
    """A 1-arg cast must receive only the value (bug B1)."""
    models.Sandwich.objects.create(data={'filling': 5})
    # A lambda (unlike the builtin `int`) gets bound as a method if
    # `create()` drops the staticmethod wrapping, so this catches B1.
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', cast=lambda value: int(value)
    )
    instance, request = make_filter(filter_class, rf, model_admin)
    instance.used_parameters = {'data__filling': '5'}
    queryset = instance.queryset(request, models.Sandwich.objects.all())
    assert queryset.count() == 1


def test_create_custom_template_and_names():
    filter_class = filters.JSONFieldFilter.create(
        'data__filling',
        title='Filling',
        parameter_name='filling',
        template='custom.html',
        timeout=datetime.timedelta(minutes=1),
    )
    assert filter_class.title == 'Filling'
    assert filter_class.parameter_name == 'filling'
    assert filter_class.template == 'custom.html'
    assert filter_class.timeout == datetime.timedelta(minutes=1)


@pytest.mark.django_db
def test_filter_variants(rf, model_admin):
    for filter_base, template in (
        (
            filters.JSONFieldFilterDropdown,
            'django_utils/admin/dropdown_filter.html',
        ),
        (
            filters.JSONFieldFilterSelect2,
            'django_utils/admin/select2_filter.html',
        ),
    ):
        filter_class = filter_base.create('data__filling')
        if template is not None:
            assert filter_class.template == template
        instance, _request = make_filter(filter_class, rf, model_admin)
        assert instance is not None


@pytest.mark.django_db
def test_select2_html_id_and_media(rf, model_admin):
    filter_class = filters.JSONFieldFilterSelect2.create('data__filling')
    instance, _request = make_filter(filter_class, rf, model_admin)
    assert instance.select_html_id() == 'data-filling'
    assert filters.Select2Mixin.Media is not None
