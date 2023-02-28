import json

from django import http, urls
from django.contrib.auth import decorators
from django.core import serializers
from django.db import models
from django.template import loader as django_loader


class ViewError(Exception):
    pass


class UnknownViewResponseError(ViewError):
    pass


def json_default_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError(
            f'Object of type {type(obj)} with value of {obj!r} is not JSON '
            'serializable'
        )


def redirect(url='./', *args, **kwargs):
    if '/' not in url or args or kwargs:
        url = urls.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponseRedirect(url)


def permanent_redirect(url, *args, **kwargs):
    if '/' not in url or args or kwargs:
        url = urls.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponsePermanentRedirect(url)


REQUEST_PROPERTIES = {
    'redirect': redirect,
    'permanent_redirect': permanent_redirect,
    'not_found': http.HttpResponseNotFound,
    'reverse': urls.reverse,
}


def _prepare_request(request, app, view):
    '''Add context and extra methods to the request'''
    request.context = dict()
    request.context['view'] = view
    request.context['app'] = app
    request.context['request'] = request

    for k, v in REQUEST_PROPERTIES.items():
        setattr(request, k, v)

    return request


def _process_response(request, response, response_class):
    '''Generic response processing function, always returns HttpResponse'''

    '''If we add something to the context stack, pop it after adding'''
    if isinstance(response, (dict, list, models.query.QuerySet)):
        if request.ajax:
            if isinstance(response, models.query.QuerySet):
                output = serializers.serialize('json', response)
            elif request.GET.get('debug'):
                from django.core.serializers import json as django_json
                output = json.dumps(
                    response,
                    indent=4,
                    sort_keys=True,
                    cls=django_json.DjangoJSONEncoder,
                    default=json_default_handler,
                )
            else:
                output = json.dumps(response, default=json_default_handler)

            callback = request.GET.get('callback', False)
            if callback:
                output = f'{callback}({output})'

            if request.GET.get('debug'):
                title = f'Rendering {request.context!r} in module ' \
                        f'{request.context!r}'

                output = f'''
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
                        <textarea>{output}</textarea>
                    </body>
                </html>
                '''
                response = response_class(output, content_type='text/html')
            else:
                response = response_class(
                    output,
                    content_type='text/plain'
                )

            return response
        else:
            '''Add the dictionary to the context and let
            render_to_response handle it'''
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


def env(function=None, login_required=False, response_class=http.HttpResponse):
    '''
    View decorator that automatically adds context and renders response

    Keyword arguments:
    login_required -- is everyone allowed or only authenticated users

    Adds a RequestContext (request.context) with the following context items:
    name -- current function name

    Stores the template in request.template and assumes it to be in
    <app>/<view>.html
    '''

    def _env(request, *args, **kwargs):
        request.ajax = bool(
            max(
                request.headers.get('x-requested-with') == 'XMLHttpRequest',
                int(request.POST.get('ajax', 0)),
                int(request.GET.get('ajax', 0)),
            )
        )
        request.context = None
        try:
            name = function.__name__
            app = function.__module__.split('.')[0]
            request = _prepare_request(request, app, name)
            request.template = f'{app}/{name}.html'
            response = function(request, *args, **kwargs)
            response = _process_response(request, response, response_class)
            return response  # pragma: no branch
        finally:
            '''Remove the context reference from request to prevent leaking'''
            try:
                del request.context, request.template
                for k in REQUEST_PROPERTIES.keys():  # pragma: no branch
                    delattr(request, k)
            except AttributeError:
                pass  # pragma: no branch

    if function:
        _env.__name__ = function.__name__
        _env.__doc__ = function.__doc__
        _env.__module__ = function.__module__
        _env.__dict__ = function.__dict__

        if login_required:
            return decorators.login_required(_env)
        else:
            return _env
    else:
        def inner(function):
            return env(function, login_required, response_class)

        return inner
