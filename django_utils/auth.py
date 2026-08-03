"""The auth helpers Django is missing.

``login_required`` and ``permission_required`` ship with Django;
``superuser_required``/``staff_required`` do not (django/new-features
#47) and get re-implemented in nearly every project.  Likewise the
``'app_label.action_modelname'`` string every ``user.has_perm()`` call
needs is hand-formatted everywhere (django/new-features #137);
``permission_string`` builds it from the model.
"""

import functools
import sys
import typing
from collections.abc import Callable

from django.contrib import auth
from django.contrib.auth import decorators as auth_decorators
from django.core import exceptions
from django.db import models

if sys.version_info >= (3, 12):
    from inspect import iscoroutinefunction
else:  # pragma: no cover
    # Same dispatch asgiref does internally, spelled so type checkers can
    # narrow it: pre-3.12, inspect.iscoroutinefunction doesn't honor
    # asgiref's `_is_coroutine` marker, so asgiref's shim is required.
    from asgiref.sync import iscoroutinefunction

_View = typing.TypeVar('_View', bound=Callable[..., typing.Any])


def _denied(
    request: typing.Any, *args: typing.Any, **kwargs: typing.Any
) -> typing.Any:  # pragma: no cover
    raise AssertionError('user_passes_test redirects before calling this')


def _denied_response(
    request: typing.Any,
    args: tuple[typing.Any, ...],
    kwargs: dict[str, typing.Any],
    raise_exception: bool,
    redirecting: Callable[..., typing.Any],
) -> typing.Any:
    if raise_exception:
        raise exceptions.PermissionDenied
    return redirecting(request, *args, **kwargs)


def _wrap_async(
    func: _View,
    check: Callable[[typing.Any], bool],
    raise_exception: bool,
    redirecting: Callable[..., typing.Any],
) -> _View:
    @functools.wraps(func)
    async def async_wrapper(
        request: typing.Any, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Any:
        if check(request.user):
            return await func(request, *args, **kwargs)
        return _denied_response(
            request, args, kwargs, raise_exception, redirecting
        )

    return typing.cast(_View, async_wrapper)


def _wrap_sync(
    func: _View,
    check: Callable[[typing.Any], bool],
    raise_exception: bool,
    redirecting: Callable[..., typing.Any],
) -> _View:
    @functools.wraps(func)
    def wrapper(
        request: typing.Any, *args: typing.Any, **kwargs: typing.Any
    ) -> typing.Any:
        if check(request.user):
            return func(request, *args, **kwargs)
        return _denied_response(
            request, args, kwargs, raise_exception, redirecting
        )

    return typing.cast(_View, wrapper)


def _flag_required(
    flag: str,
    view_func: _View | None,
    login_url: str | None,
    raise_exception: bool,
) -> '_View | Callable[[_View], _View]':
    def check(user: typing.Any) -> bool:
        return bool(getattr(user, flag, False))

    def decorator(func: _View) -> _View:
        # `django.contrib.auth.decorators.user_passes_test` only gained
        # async support in Django 5.0, so the real (possibly async) view
        # is never handed to it. `user_passes_test` only calls the
        # wrapped callable to redirect it, which happens only when
        # `check` fails -- so wrapping this never-called shim keeps the
        # redirect/login_url logic Django's own on every supported
        # version.
        redirecting = auth_decorators.user_passes_test(
            check, login_url=login_url
        )(_denied)

        if iscoroutinefunction(func):
            return _wrap_async(func, check, raise_exception, redirecting)
        return _wrap_sync(func, check, raise_exception, redirecting)

    if view_func is None:
        return decorator
    return decorator(view_func)


def superuser_required(
    view_func: _View | None = None,
    *,
    login_url: str | None = None,
    raise_exception: bool = False,
) -> '_View | Callable[[_View], _View]':
    """Allow only users with ``is_superuser``.

    Mirrors ``login_required``'s shape: use bare (``@superuser_required``)
    or parameterized (``@superuser_required(raise_exception=True)``).
    Failing users are redirected to login (``login_url`` or
    ``settings.LOGIN_URL``); with ``raise_exception=True`` they get
    ``PermissionDenied`` (HTTP 403) instead, matching
    ``permission_required``'s option of the same name. Works on both
    sync and async views.
    """
    return _flag_required(
        'is_superuser', view_func, login_url, raise_exception
    )


def staff_required(
    view_func: _View | None = None,
    *,
    login_url: str | None = None,
    raise_exception: bool = False,
) -> '_View | Callable[[_View], _View]':
    """Allow only users with ``is_staff``.  See ``superuser_required``.

    Works on both sync and async views.
    """
    return _flag_required('is_staff', view_func, login_url, raise_exception)


def permission_string(model: type[models.Model], action: str) -> str:
    """Return the ``'app_label.action_modelname'`` string ``has_perm`` wants.

    >>> from tests.test_app import models as test_models
    >>> permission_string(test_models.Sandwich, 'change')
    'test_app.change_sandwich'
    """
    meta = model._meta
    return f'{meta.app_label}.{auth.get_permission_codename(action, meta)}'
