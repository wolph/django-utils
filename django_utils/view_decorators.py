import functools
import json
import typing
from collections.abc import Callable
from typing import Any

from django import http, urls
from django.conf import settings
from django.contrib.auth import decorators
from django.core import exceptions, serializers
from django.db import models
from django.template import loader as django_loader
from django.utils.html import escape


class EnvRequest(http.HttpRequest):
    """A request as seen inside an ``env``-decorated view.

    The ``env`` decorator injects these attributes at runtime; this
    subclass exists so type checkers know about them.
    """

    ajax: bool
    context: dict[str, Any] | None
    template: str
    redirect: Callable[..., http.HttpResponseRedirect]
    permanent_redirect: Callable[..., http.HttpResponsePermanentRedirect]
    not_found: type[http.HttpResponseNotFound]
    reverse: Callable[..., str]


ViewFunction = Callable[..., Any]


class ViewError(Exception):
    pass


class UnknownViewResponseError(ViewError):
    pass


def json_default_handler(obj: Any) -> str:
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError(
            f'Object of type {type(obj)} with value of {obj!r} is not JSON '
            'serializable'
        )


def redirect(
    url: str = './', *args: Any, **kwargs: Any
) -> http.HttpResponseRedirect:
    if '/' not in url or args or kwargs:
        url = urls.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponseRedirect(url)


def permanent_redirect(
    url: str, *args: Any, **kwargs: Any
) -> http.HttpResponsePermanentRedirect:
    if '/' not in url or args or kwargs:
        url = urls.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponsePermanentRedirect(url)


REQUEST_PROPERTIES: dict[str, Any] = {
    'redirect': redirect,
    'permanent_redirect': permanent_redirect,
    'not_found': http.HttpResponseNotFound,
    'reverse': urls.reverse,
}


def _prepare_request(request: EnvRequest, app: str, view: str) -> EnvRequest:
    """Add context and extra methods to the request"""
    request.context = dict()
    request.context['view'] = view
    request.context['app'] = app
    request.context['request'] = request

    for k, v in REQUEST_PROPERTIES.items():
        setattr(request, k, v)

    return request


def _serialize_ajax_response(request: EnvRequest, response: Any) -> str:
    """Serialize a dict/list/QuerySet response body for an ajax request"""
    if isinstance(response, models.query.QuerySet):
        return serializers.serialize('json', response)
    elif request.GET.get('debug'):
        from django.core.serializers import json as django_json

        return json.dumps(
            response,
            indent=4,
            sort_keys=True,
            cls=django_json.DjangoJSONEncoder,
            default=json_default_handler,
        )
    else:
        return json.dumps(response, default=json_default_handler)


def debug_allowed(request: http.HttpRequest) -> bool:
    """Whether the ``?debug=1`` HTML view may render for this request.

    Rendering a response body inside an HTML document is a debugging
    aid, so it is restricted the way ``django-debug-toolbar`` restricts
    its own panels: ``settings.DEBUG``, or an explicitly whitelisted
    client address.

    Note that behind a reverse proxy ``REMOTE_ADDR`` is the proxy's
    address, not the client's, so ``INTERNAL_IPS`` will match nothing
    (or everything, if the proxy's own address is listed). If your
    deployment sits behind a reverse proxy and needs the real client
    address (e.g. from ``X-Forwarded-For``), reassign this function
    (``django_utils.view_decorators.debug_allowed = my_check``) rather
    than trusting that header here, since it is only meaningful when
    the proxy topology is known.
    """
    if not request.GET.get('debug'):
        return False
    if settings.DEBUG:
        return True
    return request.META.get('REMOTE_ADDR') in settings.INTERNAL_IPS


# Backwards-compatible alias for the previous private name.
_debug_allowed = debug_allowed


def _process_ajax_response(
    request: EnvRequest,
    response: Any,
    response_class: type[http.HttpResponse],
) -> http.HttpResponse:
    """Turn a dict/list/QuerySet response into an HttpResponse for ajax"""
    output = _serialize_ajax_response(request, response)

    callback = request.GET.get('callback', '')
    if callback:
        if not callback.isidentifier():
            raise exceptions.SuspiciousOperation(
                'JSONP callback must be a valid Python identifier'
            )
        output = f'{callback}({output})'

    if debug_allowed(request):
        title = escape(
            f'Rendering {request.context!r} in module {request.context!r}'
        )
        output = f"""
                <html>
                    <head>
                        <title>{title}</title>
                        <style>
                        textarea{{
                            width: 100%;
                            height: 100%;
                        }}
                        </style>
                    </head>
                    <body>
                        <textarea>{escape(output)}</textarea>
                    </body>
                </html>
                """
        return response_class(output, content_type='text/html')
    else:
        return response_class(output, content_type='text/plain')


def _process_response(
    request: EnvRequest,
    response: Any,
    response_class: type[http.HttpResponse],
) -> http.HttpResponse:
    """Generic response processing function, always returns HttpResponse"""

    """If we add something to the context stack, pop it after adding"""
    if isinstance(response, (dict, list, models.query.QuerySet)):
        if request.ajax:
            return _process_ajax_response(request, response, response_class)
        else:
            """Add the dictionary to the context and let
            render_to_response handle it"""
            assert request.context is not None
            request.context.update(response)
            response = None

    if isinstance(response, http.HttpResponse):
        return response

    elif isinstance(response, str):
        if request.ajax:
            return response_class(response, content_type='text/plain')
        else:
            return response_class(response)

    elif response is None:
        render_to_string = django_loader.render_to_string

        return response_class(
            render_to_string(
                request.template, context=request.context, request=request
            )
        )

    else:
        raise UnknownViewResponseError(
            f'"{type(response)}" is an unsupported response type'
        )


def _build_view(
    function: ViewFunction,
    login_required: bool,
    response_class: type[http.HttpResponse],
) -> Callable[..., http.HttpResponse]:
    """Wrap ``function`` in the ``env`` request/response machinery.

    Shared by both public call shapes of ``env`` so the overloaded name
    never has to be called recursively (which would match no overload).
    """

    def _env(
        request: http.HttpRequest, *args: Any, **kwargs: Any
    ) -> http.HttpResponse:
        req = typing.cast(EnvRequest, request)
        req.ajax = bool(
            max(
                req.headers.get('x-requested-with') == 'XMLHttpRequest',
                int(req.POST.get('ajax', 0)),
                int(req.GET.get('ajax', 0)),
            )
        )
        req.context = None
        try:
            # `function` is a real view function here; ty treats the generic
            # `Callable` alias as not guaranteed to expose `__name__`.
            name = function.__name__  # ty: ignore[unresolved-attribute]
            app = function.__module__.split('.')[0]
            req = _prepare_request(req, app, name)
            req.template = f'{app}/{name}.html'
            response = function(req, *args, **kwargs)
            return _process_response(
                req, response, response_class
            )  # pragma: no branch
        finally:
            """Remove the context reference from request to prevent leaking"""
            try:
                del req.context, req.template
                for k in REQUEST_PROPERTIES:  # pragma: no branch
                    delattr(req, k)
            except AttributeError:
                pass  # pragma: no branch

    functools.update_wrapper(_env, function)

    if login_required:
        return decorators.login_required(_env)
    else:
        return _env


@typing.overload
def env(function: ViewFunction) -> Callable[..., http.HttpResponse]: ...


@typing.overload
def env(
    function: None = None,
    login_required: bool = False,
    response_class: type[http.HttpResponse] = http.HttpResponse,
) -> Callable[[ViewFunction], Callable[..., http.HttpResponse]]: ...


def env(
    function: ViewFunction | None = None,
    login_required: bool = False,
    response_class: type[http.HttpResponse] = http.HttpResponse,
) -> Any:
    """
    View decorator that automatically adds context and renders response

    Keyword arguments:
    login_required -- is everyone allowed or only authenticated users

    Adds a RequestContext (request.context) with the following context items:
    name -- current function name

    Stores the template in request.template and assumes it to be in
    <app>/<view>.html
    """
    if function is not None:
        return _build_view(function, login_required, response_class)

    def inner(function: ViewFunction) -> Callable[..., http.HttpResponse]:
        return _build_view(function, login_required, response_class)

    return inner
