"""Current-request/current-user access, :mod:`contextvars`-native.

``RequestContextMiddleware`` stores each request in a
:class:`contextvars.ContextVar` for exactly the duration of its
request/response cycle, making the request reachable from code with no
``request`` argument: model ``save()`` methods, signal handlers, log
filters, template-independent helpers.

Why not a thread-local (django-crum, django-currentuser)?  Under ASGI a
single thread's event loop interleaves many requests, so thread-local
state leaks between them.  A ``ContextVar`` is isolated per asyncio task
and propagated into ``sync_to_async`` threads by asgiref, which makes it
correct under WSGI and ASGI alike.

Everything here is opt-in: without the middleware (or the
``current_request`` context manager) the getters simply return ``None``.
"""

import contextlib
import contextvars
import sys
import typing
from collections.abc import Awaitable, Callable, Generator
from typing import TYPE_CHECKING

from django import http

if sys.version_info >= (3, 12):
    from inspect import iscoroutinefunction, markcoroutinefunction
else:  # pragma: no cover
    # Same dispatch asgiref does internally, spelled so type checkers can
    # narrow it: pre-3.12, inspect.iscoroutinefunction doesn't honor
    # asgiref's `_is_coroutine` marker, so asgiref's shim is required.
    from asgiref.sync import iscoroutinefunction, markcoroutinefunction

if TYPE_CHECKING:
    from django.contrib.auth import models as auth_models

    _User = auth_models.AbstractBaseUser | auth_models.AnonymousUser

_GetResponse = Callable[[http.HttpRequest], http.HttpResponseBase]
_AsyncGetResponse = Callable[
    [http.HttpRequest], Awaitable[http.HttpResponseBase]
]

_request_var: contextvars.ContextVar[http.HttpRequest | None] = (
    contextvars.ContextVar('django_utils_request', default=None)
)


def get_current_request() -> http.HttpRequest | None:
    """Return the request currently being served, or ``None`` outside one."""
    return _request_var.get()


def get_current_user() -> '_User | None':
    """Return ``request.user`` for the current request.

    ``None`` when there is no current request or when the request has no
    ``user`` attribute (``AuthenticationMiddleware`` absent).  The user is
    read lazily off the stored request, so middleware order relative to
    ``RequestContextMiddleware`` does not matter — only that auth
    middleware ran before *this call*.
    """
    request = _request_var.get()
    if request is None:
        return None
    return getattr(request, 'user', None)


@contextlib.contextmanager
def current_request(
    request: http.HttpRequest,
) -> Generator[http.HttpRequest, None, None]:
    """Make ``request`` current for the duration of the block.

    For tests, ``shell`` sessions and management commands — anywhere no
    middleware runs.  Nests: the previous request is restored on exit.
    """
    token = _request_var.set(request)
    try:
        yield request
    finally:
        _request_var.reset(token)


class RequestContextMiddleware:
    """Store each request in the context variable for its whole cycle.

    Add to ``MIDDLEWARE`` (any position; before auth middleware is fine
    because ``get_current_user`` reads the user lazily).  The variable is
    reset in a ``finally`` so an exception anywhere downstream cannot leak
    one request into the next.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: _GetResponse | _AsyncGetResponse) -> None:
        self.get_response = get_response
        self._is_async = iscoroutinefunction(get_response)
        if self._is_async:
            # Marking the instance is Django's documented idiom for hybrid
            # middleware; typeshed types markcoroutinefunction for plain
            # functions only.
            markcoroutinefunction(self)  # ty: ignore[invalid-argument-type]

    def __call__(
        self, request: http.HttpRequest
    ) -> 'http.HttpResponseBase | Awaitable[http.HttpResponseBase]':
        if self._is_async:
            return self._acall(request)
        token = _request_var.set(request)
        try:
            return typing.cast(_GetResponse, self.get_response)(request)
        finally:
            _request_var.reset(token)

    async def _acall(self, request: http.HttpRequest) -> http.HttpResponseBase:
        token = _request_var.set(request)
        try:
            return await typing.cast(_AsyncGetResponse, self.get_response)(
                request
            )
        finally:
            _request_var.reset(token)
