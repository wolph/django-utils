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


@middleware.fetch_metadata_exempt
async def async_exempt_view(request):
    return http.HttpResponse('async exempt ok')


def slug_view(request, slug):
    return http.HttpResponse('ok')


urlpatterns = [
    urls.path('page/', echo_view),
    urls.path('exempt/', exempt_view),
    urls.path('exempt-async/', async_exempt_view),
    urls.path('page/<str:slug>/', slug_view),
]

MIDDLEWARE_UNDER_TEST = ['django_utils.middleware.FetchMetadataMiddleware']

pytestmark = pytest.mark.urls('tests.test_middleware')


@pytest.fixture(autouse=True)
def _fetch_metadata_middleware(settings):
    # `override_settings` cannot decorate plain pytest classes; the
    # `settings` fixture is the pytest-django equivalent.
    settings.MIDDLEWARE = MIDDLEWARE_UNDER_TEST


class TestSecFetchSite:
    @pytest.mark.parametrize(
        'site,method',
        [
            ('same-origin', 'post'),
            ('same-origin', 'put'),
            ('same-origin', 'patch'),
            ('same-origin', 'delete'),
            ('same-site', 'post'),
            ('same-site', 'put'),
            ('same-site', 'patch'),
            ('same-site', 'delete'),
            ('none', 'post'),
            ('none', 'put'),
            ('none', 'patch'),
            ('none', 'delete'),
        ],
    )
    def test_allowed_sites_all_unsafe_methods(self, site, method):
        client_call = getattr(Client(), method)
        response = client_call('/page/', headers={'sec-fetch-site': site})
        assert response.status_code == 200

    @pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
    def test_cross_site_rejected_all_unsafe_methods(self, method):
        client_call = getattr(Client(), method)
        response = client_call(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 403

    def test_unknown_value_rejected(self):
        # Fail closed on values the spec doesn't know.
        response = Client().post(
            '/page/', headers={'sec-fetch-site': 'whatever'}
        )
        assert response.status_code == 403

    @pytest.mark.parametrize('method', ['get', 'head', 'options', 'trace'])
    def test_safe_methods_always_pass(self, method):
        client_call = getattr(Client(), method)
        response = client_call(
            '/page/', headers={'sec-fetch-site': 'cross-site'}
        )
        assert response.status_code == 200

    @pytest.mark.parametrize(
        'site',
        [
            'Same-Origin',
            'SAME-ORIGIN',
            ' same-origin',
            'same-origin ',
            'same-origin, cross-site',
            '',
        ],
    )
    def test_case_and_edge_cases_rejected(self, site):
        # Fail closed: exact match only, no normalization.
        response = Client().post('/page/', headers={'sec-fetch-site': site})
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

    @pytest.mark.parametrize(
        'origin',
        [
            'null',
            'https://testserver',
            'http://testserver:80',
        ],
    )
    def test_origin_edge_cases_rejected(self, origin):
        # Exact match required: null, HTTPS scheme, explicit port all rejected
        response = Client().post('/page/', headers={'origin': origin})
        assert response.status_code == 403

    def test_disallowed_host_rejected(self, caplog):
        # When get_host() raises DisallowedHost, reject the request.
        import logging

        with caplog.at_level(
            logging.WARNING, logger='django_utils.middleware'
        ):
            response = Client().post(
                '/page/',
                headers={
                    'origin': 'http://x.example',
                    'host': 'evil.example',
                },
            )
        assert response.status_code == 403
        records = [
            r for r in caplog.records if r.name == 'django_utils.middleware'
        ]
        (record,) = records
        # Pins that the DisallowedHost branch, not an ordinary origin
        # mismatch, produced the 403.
        assert 'disallowed Host' in record.getMessage()


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
    from django.test import AsyncClient

    # Check that async_exempt_view is wrapped correctly
    assert sync.iscoroutinefunction(async_exempt_view)
    assert async_exempt_view.fetch_metadata_exempt is True

    # Drive the exempt async view through AsyncClient with cross-site headers
    # to verify the async wrapper body executes and the view is actually exempt
    async def scenario():
        return await AsyncClient().post(
            '/exempt-async/', headers={'sec-fetch-site': 'cross-site'}
        )

    response = sync.async_to_sync(scenario)()
    assert response.status_code == 200


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


def test_log_injection_with_newline(caplog):
    """Log injection via percent-encoded newline in URL path."""
    import logging

    with caplog.at_level(logging.WARNING, logger='django_utils.middleware'):
        # %0A is a newline; request.path decodes it, but we escape via repr()
        Client().post('/page/%0A/', headers={'sec-fetch-site': 'cross-site'})
    records = [
        r for r in caplog.records if r.name == 'django_utils.middleware'
    ]
    assert len(records) == 1, f'Expected 1 record, got {len(records)}'
    message = records[0].getMessage()
    assert '\n' not in message, 'Log message contains unescaped newline'
    assert 'cross-site' in message
