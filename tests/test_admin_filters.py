import datetime
import re

import pytest
from django.contrib import admin
from django.contrib.admin.templatetags.admin_list import admin_list_filter
from django.contrib.auth.models import User
from django.core.cache import cache as django_cache
from django.core.cache.backends.base import memcache_key_warnings
from django.core.exceptions import SuspiciousOperation
from django.test import RequestFactory
from django_utils.admin import filters

from tests.test_app import models

# Matches any `on*=` event-handler attribute (`onclick=`, `oninput=`,
# `onerror=`, ...), not just a couple of hand-picked names.
HANDLER_ATTR_RE = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)


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
def test_cache_key_is_memcached_safe(rf, model_admin):
    """The default auto-title contains spaces (see test_create_defaults);
    the cache key must still be a valid memcached key."""
    filter_class = filters.JSONFieldFilter.create('data__filling')
    instance, request = make_filter(filter_class, rf, model_admin)
    key = instance.get_lookups_cache_key(request)
    assert list(memcache_key_warnings(key)) == []
    assert len(key) <= 250

    long_querystring = '&'.join(f'param{i}=value{i}' for i in range(40))
    long_request = rf.get(f'/admin/test_app/sandwich/?{long_querystring}')
    assert len(long_request.get_full_path()) > 400
    long_key = instance.get_lookups_cache_key(long_request)
    assert list(memcache_key_warnings(long_key)) == []
    assert len(long_key) <= 250


@pytest.mark.django_db
def test_cache_key_is_stable_and_distinct(rf, model_admin):
    filter_class = filters.JSONFieldFilter.create('data__filling')
    instance_a, request = make_filter(filter_class, rf, model_admin)
    instance_b, _request = make_filter(filter_class, rf, model_admin)
    assert instance_a.get_lookups_cache_key(
        request
    ) == instance_b.get_lookups_cache_key(request)

    other_request = rf.get('/admin/test_app/sandwich/?foo=bar')
    assert instance_a.get_lookups_cache_key(
        request
    ) != instance_a.get_lookups_cache_key(other_request)

    other_title_class = filters.JSONFieldFilter.create(
        'data__filling', title='Other'
    )
    other_instance, _request = make_filter(other_title_class, rf, model_admin)
    assert instance_a.get_lookups_cache_key(
        request
    ) != other_instance.get_lookups_cache_key(request)


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


@pytest.mark.django_db
def test_lookups_obey_model_admin_queryset(rf):
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    class ScopedAdmin(admin.ModelAdmin):
        def get_queryset(self, request):
            return super().get_queryset(request).filter(data__filling='ham')

    model_admin = ScopedAdmin(models.Sandwich, admin.AdminSite())
    filter_class = filters.JSONFieldFilter.create('data__filling')
    request = rf.get('/admin/test_app/sandwich/')
    request.user = User(pk=1, is_superuser=True, is_active=True)
    instance = filter_class(request, {}, models.Sandwich, model_admin)

    values = [
        value for value, _label in instance.lookups(request, model_admin)
    ]
    assert values == ['ham']


@pytest.mark.django_db
def test_lookups_cache_is_scoped_per_user(rf, model_admin):
    models.Sandwich.objects.create(data={'filling': 'ham'})
    filter_class = filters.JSONFieldFilter.create('data__filling')

    def key_for(user_pk):
        request = rf.get('/admin/test_app/sandwich/')
        request.user = User(pk=user_pk, is_superuser=True, is_active=True)
        instance = filter_class(request, {}, models.Sandwich, model_admin)
        return instance.get_lookups_cache_key(request)

    assert key_for(1) != key_for(2)
    assert key_for(1) == key_for(1)


@pytest.mark.django_db
def test_lookups_cache_does_not_leak_across_users(rf):
    """End-to-end: user 1's cached lookups must not be served to user 2
    when the ModelAdmin scopes rows differently per user (bug B-leak)."""
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    class PerUserAdmin(admin.ModelAdmin):
        def get_queryset(self, request):
            queryset = super().get_queryset(request)
            if request.user.pk == 1:
                return queryset.filter(data__filling='ham')
            return queryset.filter(data__filling='cheese')

    model_admin = PerUserAdmin(models.Sandwich, admin.AdminSite())
    filter_class = filters.JSONFieldFilter.create('data__filling')

    # User 1 populates the cache with their own (ham-only) view.
    request_1 = rf.get('/admin/test_app/sandwich/')
    request_1.user = User(pk=1, is_superuser=True, is_active=True)
    instance_1 = filter_class(request_1, {}, models.Sandwich, model_admin)
    values_1 = [
        value for value, _label in instance_1.lookups(request_1, model_admin)
    ]
    assert values_1 == ['ham']

    # User 2, with a different visible row set, must not receive user 1's
    # cached (ham) values.
    request_2 = rf.get('/admin/test_app/sandwich/')
    request_2.user = User(pk=2, is_superuser=True, is_active=True)
    instance_2 = filter_class(request_2, {}, models.Sandwich, model_admin)
    values_2 = [
        value for value, _label in instance_2.lookups(request_2, model_admin)
    ]
    assert values_2 == ['cheese']


@pytest.mark.django_db
def test_queryset_via_admin_changelist(rf):
    """Exercise Django's own request -> value parsing end to end."""
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    filter_class = filters.JSONFieldFilter.create('data__filling')

    class SandwichAdmin(admin.ModelAdmin):
        list_filter = (filter_class,)

    model_admin = SandwichAdmin(models.Sandwich, admin.AdminSite())
    request = rf.get('/admin/test_app/sandwich/', {'data__filling': 'ham'})
    request.user = User(is_superuser=True, is_active=True, is_staff=True)

    changelist = model_admin.get_changelist_instance(request)
    assert changelist.get_queryset(request).count() == 1


def test_declaring_an_unsupported_operator_is_a_configuration_error():
    with pytest.raises(ValueError, match='not_an_operator'):
        filters.JSONFieldFilter.create(
            'data__filling', operators=('not_an_operator',)
        )


@pytest.mark.django_db()
def test_operator_from_the_query_string_must_be_allowlisted(rf, model_admin):
    models.Sandwich.objects.create(data={'filling': 'ham'})
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )
    request = rf.get('/admin/test_app/sandwich/')
    instance = filter_class(request, {}, models.Sandwich, model_admin)

    instance.used_parameters = {
        'data__filling': 'ham',
        'data__filling__op': 'exact',
    }
    assert instance.get_operator() == 'exact'

    instance.used_parameters = {
        'data__filling': 'ham',
        'data__filling__op': 'regex',
    }
    with pytest.raises(SuspiciousOperation):
        instance.get_operator()


@pytest.mark.django_db()
def test_operator_param_normalizes_string_and_list_valued_params(
    rf, model_admin
):
    """Django 4.2 passes scalar-string `params` to a filter's __init__;
    Django >=5.0 passes list-valued `params` and itself takes the last
    element (see `SimpleListFilter.__init__`). `value[-1]` on a *string*
    silently yields its last character ('icontains' -> 's') instead of
    raising, so both shapes must be exercised directly -- going only
    through `RequestFactory` exercises whichever single shape the
    locally installed Django version happens to produce and would hide
    a regression in the other."""
    models.Sandwich.objects.create(data={'filling': 'ham'})
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )
    request = rf.get('/admin/test_app/sandwich/')

    # Django 4.2 shape: scalar strings.
    string_valued = filter_class(
        request,
        {'data__filling': 'ham', 'data__filling__op': 'icontains'},
        models.Sandwich,
        model_admin,
    )
    assert string_valued.get_operator() == 'icontains'

    # Django >=5.0 shape: list-valued.
    list_valued = filter_class(
        request,
        {'data__filling': ['ham'], 'data__filling__op': ['icontains']},
        models.Sandwich,
        model_admin,
    )
    assert list_valued.get_operator() == 'icontains'


def test_numeric_operator_without_cast_is_a_configuration_error():
    with pytest.raises(ValueError, match='cast'):
        filters.JSONFieldFilter.create('data__price', operators=('gte',))

    filter_class = filters.JSONFieldFilter.create(
        'data__price', operators=('gte',), cast=int
    )
    assert filter_class.operators == ('gte',)


def test_create_with_empty_operators_is_a_configuration_error():
    with pytest.raises(ValueError):
        filters.JSONFieldFilter.create('data__filling', operators=())


@pytest.mark.django_db
def test_queryset_via_admin_changelist_with_operator(rf):
    """The operator param must be claimed by expected_parameters(), or
    Django's ChangeList treats it as a leftover ORM lookup (re-parsed as
    a JSONField key transform, e.g. ``data->filling->op``) and silently
    returns zero rows instead of applying the filter."""
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )

    class SandwichAdmin(admin.ModelAdmin):
        list_filter = (filter_class,)

    model_admin = SandwichAdmin(models.Sandwich, admin.AdminSite())
    request = rf.get(
        '/admin/test_app/sandwich/',
        {'data__filling': 'ham', 'data__filling__op': 'exact'},
    )
    request.user = User(is_superuser=True, is_active=True, is_staff=True)

    changelist = model_admin.get_changelist_instance(request)
    assert changelist.get_queryset(request).count() == 1


@pytest.mark.django_db()
def test_omitting_operators_keeps_exact_match_behaviour(rf, model_admin):
    """Backwards compatibility: create() without operators is unchanged."""
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'hamburger'})

    filter_class = filters.JSONFieldFilter.create('data__filling')
    request = rf.get('/admin/test_app/sandwich/')
    instance = filter_class(request, {}, models.Sandwich, model_admin)
    instance.used_parameters = {'data__filling': 'ham'}

    assert (
        instance.queryset(request, models.Sandwich.objects.all()).count() == 1
    )


@pytest.mark.django_db()
def test_icontains_operator_filters_a_json_subpath(rf, model_admin):
    """The brief's own `contains` example does not work here -- see
    `test_contains_operator_is_rejected_at_create_time` below -- so
    this proves the operator-suffix mechanism itself using `icontains`,
    which `KeyTransform` (unlike bare `contains`) registers directly.
    """
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'hamburger'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )
    request = rf.get('/admin/test_app/sandwich/')
    instance = filter_class(request, {}, models.Sandwich, model_admin)
    instance.used_parameters = {
        'data__filling': 'ham',
        'data__filling__op': 'icontains',
    }

    assert (
        instance.queryset(request, models.Sandwich.objects.all()).count() == 2
    )


def test_contains_operator_is_rejected_at_create_time():
    """`contains` is a member of the generic `SUPPORTED_OPERATORS`
    allowlist -- it's legitimate for ordinary (non-JSON) fields -- but
    once applied to a JSON sub-path (a `KeyTransform`, which is all
    `JSONFieldFilter.create()` ever builds), it does not do what an
    admin user picking it from the dropdown would expect.

    `KeyTransform` registers a lookup for `icontains` directly, but not
    for bare `contains`. Lookup resolution then falls through to
    `KeyTransform.output_field`, a plain `JSONField()`, which *does*
    register `contains` -- as `DataContains`, Postgres's `@>`
    JSON-containment operator, not a text substring test. That raises
    `NotSupportedError` outright on SQLite (no `supports_json_field_
    contains`); on PostgreSQL it would not raise, but for a scalar RHS
    containment degrades to equality, so it would silently behave like
    `exact` instead of a substring match. This is a pre-existing Django
    JSONField/KeyTransform limitation, not a regression introduced by
    `queryset()`'s operator suffix -- see task-4-report.md. `create()`
    now rejects it up front so the failure is at import time, not at
    request time (or, worse, not at all on PostgreSQL).
    """
    with pytest.raises(ValueError, match='icontains'):
        filters.JSONFieldFilter.create(
            'data__filling', operators=('exact', 'contains')
        )


def test_range_operator_is_rejected_at_create_time():
    """`range` expects a two-element sequence; a filter only ever
    supplies a single scalar value from the query string, so it fails
    at request time with a confusing `TypeError` from deep inside the
    SQL compiler rather than a clear error. `cast=int` is passed here
    to isolate this guard from the separate numeric-without-cast
    guard above.
    """
    with pytest.raises(ValueError):
        filters.JSONFieldFilter.create(
            'data__filling', operators=('range',), cast=int
        )


@pytest.mark.django_db
def test_expected_parameters_includes_operator_param(rf, model_admin):
    """`FacetsMixin.get_facet_queryset` consults `expected_parameters()`
    to exclude a filter's own params when computing its facet counts; it
    must list both the value and the operator parameter."""
    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )
    instance, _request = make_filter(filter_class, rf, model_admin)
    assert instance.expected_parameters() == [
        'data__filling',
        'data__filling__op',
    ]


@pytest.mark.django_db
def test_queryset_via_admin_changelist_with_non_exact_operator(rf):
    """Exercise the operator-suffixed lookup added to `queryset()` in
    this task through real admin request -> value parsing, not a
    hand-set `used_parameters` dict. Task 3's own operator handling had
    a silent wrong-results bug that only a real changelist request
    could surface (see `test_queryset_via_admin_changelist_with_
    operator` above); this is the equivalent guard for the operator
    actually being appended to the lookup rather than ignored.
    """
    models.Sandwich.objects.create(data={'filling': 'ham'})
    models.Sandwich.objects.create(data={'filling': 'hamburger'})
    models.Sandwich.objects.create(data={'filling': 'cheese'})

    filter_class = filters.JSONFieldFilter.create(
        'data__filling', operators=('exact', 'icontains')
    )

    class SandwichAdmin(admin.ModelAdmin):
        list_filter = (filter_class,)

    model_admin = SandwichAdmin(models.Sandwich, admin.AdminSite())
    request = rf.get(
        '/admin/test_app/sandwich/',
        {'data__filling': 'ham', 'data__filling__op': 'icontains'},
    )
    request.user = User(is_superuser=True, is_active=True, is_staff=True)

    changelist = model_admin.get_changelist_instance(request)
    assert changelist.get_queryset(request).count() == 2


def _render_lookup_filter(rf, model_admin, get_params):
    """Render `lookup_filter.html` through the real admin pipeline --
    `get_changelist_instance()` -> `admin_list_filter()` -- exactly how
    `change_list.html` renders it, and return the markup. Exercising the
    template this way (instead of calling `Template.render()` on a
    hand-built context) is what catches what template coverage can't:
    template code is invisible to coverage.py, so a broken `lookup_
    filter.html` -- as it was before this fix -- produces no coverage
    gap, only silently wrong HTML.
    """
    request = rf.get('/admin/test_app/sandwich/', get_params)
    request.user = User(is_superuser=True, is_active=True, is_staff=True)
    changelist = model_admin.get_changelist_instance(request)
    (spec,) = changelist.filter_specs
    return str(admin_list_filter(changelist, spec))


@pytest.fixture
def lookup_filter_admin():
    # `SimpleListFilter.has_output()` (which `ChangeList.get_filters()`
    # consults to decide whether to include a filter in `filter_specs`
    # at all) defaults to `bool(self.lookup_choices)`, so a filter whose
    # `lookups()` finds no rows is silently omitted -- at least one row
    # is required for `filter_specs` to be non-empty below.
    models.Sandwich.objects.create(data={'price': 10})

    filter_class = filters.JSONFieldFilter.create(
        'data__price',
        operators=('exact', 'gte'),
        cast=int,
        template='django_utils/admin/lookup_filter.html',
    )

    class SandwichAdmin(admin.ModelAdmin):
        list_display = ('id',)
        list_filter = (filter_class,)

    return SandwichAdmin(models.Sandwich, admin.AdminSite())


@pytest.mark.django_db
def test_lookup_filter_operator_select_lists_operators_and_marks_current(
    rf, lookup_filter_admin
):
    rendered = _render_lookup_filter(
        rf,
        lookup_filter_admin,
        {'data__price': '10', 'data__price__op': 'gte'},
    )

    assert 'django_utils/admin/lookup_filter.css' in rendered
    assert re.findall(r'<option value="([a-z]+)"', rendered) == [
        'exact',
        'gte',
    ]
    assert '<option value="gte" selected="selected">gte</option>' in rendered
    assert '<option value="exact" selected="selected">' not in rendered


@pytest.mark.django_db
def test_lookup_filter_hidden_inputs_preserve_other_query_state(
    rf, lookup_filter_admin
):
    """`q=search-term` is the load-bearing assertion: rendering it reads
    `spec.request`, which Django's `ListFilter.__init__` only sets on
    >=5.0 (see `LookupFilterMixin.__init__`). On 4.2, before that fix,
    `spec.request` doesn't exist; a template silently resolves a missing
    attribute to '' rather than raising, so the hidden-input loop
    iterates over nothing and this assertion fails.

    `_popup=1&_popup=2` -- a real, Django-recognised query param that is
    always stripped before it reaches the ORM (`IS_POPUP_VAR` is one of
    `ChangeList`'s `IGNORED_PARAMS`), so it is safe to repeat without
    also being claimed by a filter -- checks that a repeated key
    round-trips as one hidden input per value instead of collapsing to
    the last one.
    """
    rendered = _render_lookup_filter(
        rf,
        lookup_filter_admin,
        {
            'data__price': '10',
            'data__price__op': 'gte',
            'q': 'search-term',
            '_popup': ['1', '2'],
        },
    )

    assert '<input type="hidden" name="q" value="search-term">' in rendered
    assert '<input type="hidden" name="_popup" value="1">' in rendered
    assert '<input type="hidden" name="_popup" value="2">' in rendered
    assert rendered.count('name="_popup"') == 2

    # The filter's own params are rendered as the visible select/input,
    # never duplicated as hidden inputs.
    assert '<input type="hidden" name="data__price"' not in rendered
    assert '<input type="hidden" name="data__price__op"' not in rendered


@pytest.mark.django_db
def test_lookup_filter_markup_is_csp_safe(rf, lookup_filter_admin):
    rendered = _render_lookup_filter(
        rf,
        lookup_filter_admin,
        {'data__price': '10', 'data__price__op': 'gte'},
    )

    assert 'style=' not in rendered.lower()
    assert not HANDLER_ATTR_RE.search(rendered)
