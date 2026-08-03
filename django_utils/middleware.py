"""Standalone middleware.

``FetchMetadataMiddleware`` implements modern, header-based CSRF
protection (the approach django/new-features #98 proposes for core and
Go's standard library ships): browsers have sent the ``Sec-Fetch-Site``
request header on every request since roughly 2019, so cross-site
state-changing requests can be rejected without tokens, template tags or
AJAX header plumbing.

Deliberately defense-in-depth: run it *alongside*
``CsrfViewMiddleware``, never instead of it.  A request carrying neither
``Sec-Fetch-Site`` nor ``Origin`` (an old browser, curl, a server-side
client) is allowed through — rejecting those is exactly the token
middleware's job, which is why this middleware alone is not sufficient
protection.
"""

import functools
import logging
import sys
import typing
from collections.abc import Awaitable, Callable

from django import http
from django.core import exceptions

if sys.version_info >= (3, 12):
    from inspect import iscoroutinefunction, markcoroutinefunction
else:  # pragma: no cover
    # Same dispatch asgiref does internally, spelled so type checkers can
    # narrow it (asgiref's own re-export trips reportDeprecated on 3.12+):
    # pre-3.12, inspect.iscoroutinefunction doesn't honor asgiref's
    # `_is_coroutine` marker, so asgiref's shim is required.
    from asgiref.sync import iscoroutinefunction, markcoroutinefunction

logger = logging.getLogger(__name__)

SAFE_METHODS = frozenset({'GET', 'HEAD', 'OPTIONS', 'TRACE'})
_ALLOWED_SITES = frozenset({'same-origin', 'same-site', 'none'})

_View = typing.TypeVar('_View', bound=Callable[..., typing.Any])
_GetResponse = Callable[[http.HttpRequest], http.HttpResponseBase]
_AsyncGetResponse = Callable[
    [http.HttpRequest], Awaitable[http.HttpResponseBase]
]


def fetch_metadata_exempt(view_func: _View) -> _View:
    """Mark a view as exempt from ``FetchMetadataMiddleware``.

    Same shape as ``csrf_exempt``; works on sync and async views.
    """
    if iscoroutinefunction(view_func):

        @functools.wraps(view_func)
        async def wrapper(  # pyright: ignore[reportRedeclaration]
            *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            return await view_func(*args, **kwargs)

    else:

        @functools.wraps(view_func)
        def wrapper(  # pyright: ignore[reportRedeclaration]
            *args: typing.Any, **kwargs: typing.Any
        ) -> typing.Any:
            return view_func(*args, **kwargs)

    wrapper.fetch_metadata_exempt = True  # type: ignore[attr-defined]  # ty: ignore[invalid-assignment]
    return typing.cast(_View, wrapper)


class FetchMetadataMiddleware:
    """Reject cross-site state-changing requests by request headers.

    Policy, in order:

    1. Safe methods (GET/HEAD/OPTIONS/TRACE) always pass.
    2. Views marked ``@fetch_metadata_exempt`` pass.
    3. ``Sec-Fetch-Site`` present: allow ``same-origin``/``same-site``/
       ``none`` (browser UI, e.g. the address bar); reject anything else
       with 403 — unknown values fail closed.
    4. No ``Sec-Fetch-Site``: compare ``Origin`` to this request's
       ``scheme://host``; mismatch is rejected.
    5. Neither header: allow.  Token CSRF remains the backstop.

    Behind a TLS-terminating proxy, step 4 can false-reject: without
    ``SECURE_PROXY_SSL_HEADER`` configured, ``request.scheme`` reads
    ``http`` while a legacy browser's ``Origin`` header (the client sees
    only the outer HTTPS connection) is ``https://…``, so the exact-match
    comparison fails and the request is rejected as cross-site. Modern
    browsers are unaffected -- they send ``Sec-Fetch-Site``, which step 3
    handles first. Configure ``SECURE_PROXY_SSL_HEADER`` per the Django
    docs to fix ``request.scheme`` itself.
    """

    sync_capable = True
    async_capable = True

    def __init__(self, get_response: _GetResponse | _AsyncGetResponse) -> None:
        self.get_response: _GetResponse | _AsyncGetResponse = get_response
        self._is_async: bool = iscoroutinefunction(get_response)
        if self._is_async:
            # Marking the instance is Django's documented idiom for hybrid
            # middleware; typeshed types markcoroutinefunction for plain
            # functions only.
            markcoroutinefunction(self)  # ty: ignore[invalid-argument-type]

    def __call__(
        self, request: http.HttpRequest
    ) -> http.HttpResponseBase | Awaitable[http.HttpResponseBase]:
        if self._is_async:
            return typing.cast(_AsyncGetResponse, self.get_response)(request)
        return typing.cast(_GetResponse, self.get_response)(request)

    def process_view(
        self,
        request: http.HttpRequest,
        callback: Callable[..., typing.Any],
        callback_args: tuple[typing.Any, ...],
        callback_kwargs: dict[str, typing.Any],
    ) -> http.HttpResponseBase | None:
        if request.method in SAFE_METHODS:
            return None
        if getattr(callback, 'fetch_metadata_exempt', False):
            return None
        site = request.headers.get('Sec-Fetch-Site')
        if site is not None:
            if site in _ALLOWED_SITES:
                return None
            return self._reject(request, f'Sec-Fetch-Site is {site[:64]!r}')
        origin = request.headers.get('Origin')
        if origin is None:
            return None
        try:
            expected = f'{request.scheme}://{request.get_host()}'
        except exceptions.DisallowedHost:
            return self._reject(
                request, f'Origin {origin[:64]!r} with disallowed Host'
            )
        if origin == expected:
            return None
        return self._reject(
            request, f'Origin {origin[:64]!r} does not match {expected!r}'
        )

    def _reject(
        self, request: http.HttpRequest, reason: str
    ) -> http.HttpResponseForbidden:
        logger.warning(
            'Fetch-Metadata policy rejected %s %.200r: %.200s',
            request.method,
            request.get_full_path(),
            reason,
        )
        return http.HttpResponseForbidden(
            'Cross-site request rejected by Fetch-Metadata policy.'
        )
