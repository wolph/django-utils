"""Tests for django_utils.context.

The middleware tests go through the real test client (WSGI) and the real
ASGI handler (via async_to_sync) rather than calling the middleware
directly: context isolation between concurrent requests is the entire
point of the module and only shows up under the real handlers.
"""

import asyncio

import pytest
from asgiref import sync
from django import http, urls
from django.test import Client
from django_utils import context

MIDDLEWARE_WITH_CONTEXT = [
    'django_utils.context.RequestContextMiddleware',
]

# This module doubles as the urlconf (pytest.mark.urls below).
pytestmark = pytest.mark.urls('tests.test_context')


@pytest.fixture(autouse=True)
def _context_middleware(settings):
    # `override_settings` cannot decorate plain pytest classes (it only
    # accepts SimpleTestCase subclasses); pytest-django's `settings`
    # fixture is the idiomatic equivalent.
    settings.MIDDLEWARE = MIDDLEWARE_WITH_CONTEXT


def plain_view(request):
    current = context.get_current_request()
    return http.JsonResponse({'is_current': current is request})


def raising_view(request):
    raise RuntimeError('boom')


async def async_view(request):
    # Sleep so two gathered requests genuinely overlap on the event loop.
    await asyncio.sleep(0.02)
    current = context.get_current_request()
    return http.JsonResponse(
        {
            'is_current': current is request,
            'marker': request.GET.get('marker'),
        }
    )


urlpatterns = [
    urls.path('plain/', plain_view),
    urls.path('raising/', raising_view),
    urls.path('async/', async_view),
]


class TestSyncMiddleware:
    def test_view_sees_its_own_request(self):
        response = Client().get('/plain/')
        assert response.json() == {'is_current': True}

    def test_reset_after_response(self):
        Client().get('/plain/')
        assert context.get_current_request() is None

    def test_reset_after_view_exception(self):
        Client(raise_request_exception=False).get('/raising/')
        assert context.get_current_request() is None


def test_concurrent_async_requests_are_isolated():
    from django.test import AsyncClient

    async def scenario():
        client_a = AsyncClient()
        client_b = AsyncClient()
        return await asyncio.gather(
            client_a.get('/async/', {'marker': 'a'}),
            client_b.get('/async/', {'marker': 'b'}),
        )

    response_a, response_b = sync.async_to_sync(scenario)()
    assert response_a.json() == {'is_current': True, 'marker': 'a'}
    assert response_b.json() == {'is_current': True, 'marker': 'b'}


def test_no_middleware_returns_none():
    assert context.get_current_request() is None
    assert context.get_current_user() is None


def test_current_request_context_manager(rf):
    request = rf.get('/')
    with context.current_request(request) as active:
        assert active is request
        assert context.get_current_request() is request
    assert context.get_current_request() is None


def test_current_request_nests(rf):
    outer, inner = rf.get('/outer'), rf.get('/inner')
    with context.current_request(outer):
        with context.current_request(inner):
            assert context.get_current_request() is inner
        assert context.get_current_request() is outer


def test_get_current_user_reads_request_user(rf, django_user_model):
    request = rf.get('/')
    request.user = django_user_model(username='alice')
    with context.current_request(request):
        assert context.get_current_user() is request.user


def test_get_current_user_without_auth_middleware(rf):
    # A request that never went through AuthenticationMiddleware has no
    # `user` attribute; that must read as None, not AttributeError.
    with context.current_request(rf.get('/')):
        assert context.get_current_user() is None
