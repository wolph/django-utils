"""The auth helpers Django is missing.

``login_required`` and ``permission_required`` ship with Django;
``superuser_required``/``staff_required`` do not (django/new-features
#47) and get re-implemented in nearly every project.  Likewise the
``'app_label.action_modelname'`` string every ``user.has_perm()`` call
needs is hand-formatted everywhere (django/new-features #137);
``permission_string`` builds it from the model.
"""

import functools
import typing
from collections.abc import Callable

from django.contrib import auth
from django.contrib.auth import decorators as auth_decorators
from django.core import exceptions
from django.db import models

_View = typing.TypeVar('_View', bound=Callable[..., typing.Any])


def _flag_required(
    flag: str,
    view_func: _View | None,
    login_url: str | None,
    raise_exception: bool,
) -> '_View | Callable[[_View], _View]':
    def check(user: typing.Any) -> bool:
        return bool(getattr(user, flag, False))

    def decorator(func: _View) -> _View:
        redirecting = auth_decorators.user_passes_test(
            check, login_url=login_url
        )(func)

        @functools.wraps(func)
        def wrapper(
            request: typing.Any, *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            if check(request.user):
                return func(request, *args, **kwargs)
            if raise_exception:
                raise exceptions.PermissionDenied
            return redirecting(request, *args, **kwargs)

        return typing.cast(_View, wrapper)

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
    ``permission_required``'s option of the same name.
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
    """Allow only users with ``is_staff``.  See ``superuser_required``."""
    return _flag_required('is_staff', view_func, login_url, raise_exception)


def permission_string(model: type[models.Model], action: str) -> str:
    """Return the ``'app_label.action_modelname'`` string ``has_perm`` wants.

    >>> from tests.test_app import models as test_models
    >>> permission_string(test_models.Sandwich, 'change')
    'test_app.change_sandwich'
    """
    meta = model._meta
    return f'{meta.app_label}.{auth.get_permission_codename(action, meta)}'
