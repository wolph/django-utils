"""Tests for django_utils.auth."""

import pytest
from asgiref import sync
from django import http
from django.contrib.auth import models as auth_models
from django.core import exceptions
from django_utils import auth

from tests.test_app import models


def ok_view(request):
    return http.HttpResponse('ok')


async def async_ok_view(request):
    return http.HttpResponse('ok')


def _request(rf, user):
    request = rf.get('/restricted/')
    request.user = user
    return request


@pytest.fixture
def superuser():
    return auth_models.User(username='root', is_superuser=True, is_staff=True)


@pytest.fixture
def staff():
    return auth_models.User(username='staff', is_staff=True)


@pytest.fixture
def plain_user():
    return auth_models.User(username='plain')


def test_superuser_required_allows_superuser(rf, superuser):
    view = auth.superuser_required(ok_view)
    assert view(_request(rf, superuser)).status_code == 200


def test_superuser_required_redirects_staff(rf, staff):
    view = auth.superuser_required(ok_view)
    response = view(_request(rf, staff))
    assert response.status_code == 302
    assert response.url.startswith('/accounts/login/')


def test_superuser_required_custom_login_url(rf, plain_user):
    view = auth.superuser_required(login_url='/other-login/')(ok_view)
    response = view(_request(rf, plain_user))
    assert response.status_code == 302
    assert response.url.startswith('/other-login/')


def test_superuser_required_raise_exception(rf, staff):
    view = auth.superuser_required(raise_exception=True)(ok_view)
    with pytest.raises(exceptions.PermissionDenied):
        view(_request(rf, staff))


def test_superuser_required_anonymous_redirects(rf):
    view = auth.superuser_required(ok_view)
    assert view(_request(rf, auth_models.AnonymousUser())).status_code == 302


def test_staff_required_allows_staff(rf, staff):
    view = auth.staff_required(ok_view)
    assert view(_request(rf, staff)).status_code == 200


def test_staff_required_blocks_plain_user(rf, plain_user):
    view = auth.staff_required(raise_exception=True)(ok_view)
    with pytest.raises(exceptions.PermissionDenied):
        view(_request(rf, plain_user))


def test_superuser_required_anonymous_raise_exception(rf):
    view = auth.superuser_required(raise_exception=True)(ok_view)
    with pytest.raises(exceptions.PermissionDenied):
        view(_request(rf, auth_models.AnonymousUser()))


def test_superuser_required_allows_async_superuser(rf, superuser):
    decorated = auth.superuser_required(async_ok_view)
    assert sync.iscoroutinefunction(decorated)
    response = sync.async_to_sync(decorated)(_request(rf, superuser))
    assert response.status_code == 200


def test_superuser_required_redirects_async_staff(rf, staff):
    decorated = auth.superuser_required(login_url='/other-login/')(
        async_ok_view
    )
    response = sync.async_to_sync(decorated)(_request(rf, staff))
    assert response.status_code == 302
    assert response.url.startswith('/other-login/')


def test_staff_required_async_raise_exception_blocks_plain_user(
    rf, plain_user
):
    decorated = auth.staff_required(raise_exception=True)(async_ok_view)
    with pytest.raises(exceptions.PermissionDenied):
        sync.async_to_sync(decorated)(_request(rf, plain_user))


def test_decorators_preserve_view_metadata():
    assert auth.superuser_required(ok_view).__name__ == 'ok_view'
    assert auth.staff_required(raise_exception=True)(ok_view).__name__ == (
        'ok_view'
    )


def test_permission_string():
    assert auth.permission_string(models.Sandwich, 'change') == (
        'test_app.change_sandwich'
    )
    assert auth.permission_string(models.Sandwich, 'view') == (
        'test_app.view_sandwich'
    )


@pytest.mark.django_db
def test_permission_string_round_trips_through_has_perm(superuser):
    superuser.save()
    assert superuser.has_perm(auth.permission_string(models.Sandwich, 'add'))
