"""Tests for django_utils.middleware.FetchMetadataMiddleware.

The whole deliverable is the policy matrix, so the tests enumerate it
explicitly instead of sampling it.
"""

import pytest
from django import http, urls
from django.test import Client
from django_utils import middleware


def echo_view(request):
    return http.HttpResponse('ok')


@middleware.fetch_metadata_exempt
def exempt_view(request):
    return http.HttpResponse('exempt ok')


urlpatterns = [
    urls.path('page/', echo_view),
    urls.path('exempt/', exempt_view),
]

MIDDLEWARE_UNDER_TEST = ['django_utils.middleware.FetchMetadataMiddleware']

pytestmark = pytest.mark.urls('tests.test_middleware')


@pytest.fixture(autouse=True)
def _fetch_metadata_middleware(settings):
    # `override_settings` cannot decorate plain pytest classes; the
    # `settings` fixture is the pytest-django equivalent.
    settings.MIDDLEWARE = MIDDLEWARE_UNDER_TEST


class TestSecFetchSite:
    @pytest.mark.parametrize('site', ['same-origin', 'same-site', 'none'])
    def test_allowed_sites_post(self, site):
        response = Client().post('/page/', headers={'sec-fetch-site': site})
        assert response.status_code == 200

    def test_cross_site_post_rejected(self):
        response = Client().post(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 403

    def test_unknown_value_rejected(self):
        # Fail closed on values the spec doesn't know.
        response = Client().post(
            '/page/', headers={'sec-fetch-site': 'whatever'}
        )
        assert response.status_code == 403

    @pytest.mark.parametrize('method', ['get', 'head', 'options'])
    def test_safe_methods_always_pass(self, method):
        client_call = getattr(Client(), method)
        response = client_call(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 200

    @pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
    def test_all_unsafe_methods_covered(self, method):
        client_call = getattr(Client(), method)
        response = client_call(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 403


class TestOriginFallback:
    def test_matching_origin_allowed(self):
        response = Client().post(
            '/page/', headers={'origin': 'http://testserver'}
        )
        assert response.status_code == 200

    def test_mismatched_origin_rejected(self):
        response = Client().post(
            '/page/', headers={'origin': 'https://evil.example'}
        )
        assert response.status_code == 403

    def test_no_headers_allowed(self):
        # No Sec-Fetch-Site, no Origin: old browser or non-browser
        # client.  Explicitly allowed; token CSRF is the backstop.
        assert Client().post('/page/').status_code == 200

    def test_sec_fetch_site_wins_over_origin(self):
        # Header present -> Origin is not consulted at all.
        response = Client().post(
            '/page/',
            headers={
                'sec-fetch-site': 'same-origin',
                'origin': 'https://evil.example',
            },
        )
        assert response.status_code == 200


class TestExemption:
    def test_exempt_view_allows_cross_site(self):
        response = Client().post(
            '/exempt/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 200

    def test_exempt_preserves_metadata(self):
        assert exempt_view.__name__ == 'exempt_view'


def test_exempt_wraps_async_views():
    from asgiref import sync

    @middleware.fetch_metadata_exempt
    async def async_view(request):
        return http.HttpResponse('ok')

    assert sync.iscoroutinefunction(async_view)
    assert async_view.fetch_metadata_exempt is True


def test_rejection_logs_warning(caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger='django_utils.middleware'):
        Client().post('/page/', headers={'sec-fetch-site': 'cross-site'})
    records = [
        r for r in caplog.records if r.name == 'django_utils.middleware'
    ]
    (record,) = records
    assert 'cross-site' in record.getMessage()
    assert '/page/' in record.getMessage()


def test_async_stack():
    from asgiref import sync
    from django.test import AsyncClient

    async def scenario():
        return await AsyncClient().post(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )

    assert sync.async_to_sync(scenario)().status_code == 403


def test_async_exempt_view_called():
    """Test async wrapper in fetch_metadata_exempt actually executes."""
    from asgiref import sync

    @middleware.fetch_metadata_exempt
    async def async_exempt_view(request):
        return http.HttpResponse('async exempt ok')

    # Test that the wrapped async view can be called
    async def scenario():
        # Call the view function directly to test the wrapper executes
        response = await async_exempt_view(None)
        return response.status_code == 200

    result = sync.async_to_sync(scenario)()
    assert result
