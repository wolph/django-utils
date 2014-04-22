import json
from django import shortcuts as django_shortcuts
from django.template import loader as django_loader
from django import http
from django.template import RequestContext
from django.contrib.auth import decorators
from django.conf import settings
from django.core import serializers
from django.db import models
from django.core import urlresolvers

try:
    from coffin import shortcuts as coffin_shortcuts
except ImportError:
    coffin_shortcuts = None


class ViewError(Exception):
    pass


class UnknownViewResponseError(ViewError):
    pass


def json_default_handler(obj):
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    else:
        raise TypeError('Object of type %s with value of %s is not JSON '
                        'serializable' % (type(obj), repr(obj)))


def redirect(url='./', *args, **kwargs):
    if '/' not in url or args or kwargs:
        url = urlresolvers.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponseRedirect(url)


def permanent_redirect(url, *args, **kwargs):
    if '/' not in url or args or kwargs:
        url = urlresolvers.reverse(url, args=args, kwargs=kwargs)
    return http.HttpResponsePermanentRedirect(url)


REQUEST_PROPERTIES = {
    'redirect': redirect,
    'permanent_redirect': permanent_redirect,
    'not_found': http.HttpResponseNotFound,
    'reverse': urlresolvers.reverse,
}


def _prepare_request(request, app, view):
    '''Add context and extra methods to the request'''
    request.context = RequestContext(request)
    request.context['view'] = view
    request.context['app'] = app
    request.context['request'] = request

    for k, v in REQUEST_PROPERTIES.iteritems():
        setattr(request, k, v)

    return request


def _process_response(request, response, response_class):
    '''Generic response processing function, always returns HttpResponse'''

    '''If we add something to the context stack, pop it after adding'''
    pop = False

    try:
        if isinstance(response, (dict, list, models.query.QuerySet)):
            if request.ajax:
                if isinstance(response, models.query.QuerySet):
                    output = serializers.serialize('json', response)
                else:
                    output = json.dumps(response, default=json_default_handler)

                callback = request.GET.get('callback', False)
                if callback:
                    output = '%s(%s)' % (callback, output)
                if request.GET.get('debug'):
                    title = 'Rendering %(view)r in module %(app)r' % (
                        request.context)

                    output = '''
                    <html>
                        <head>
                            <title>%s</title>
                        </head>
                        <body>
                            <textarea>%s</textarea>
                        </body>
                    </html>
                    ''' % (title, output)
                    response = response_class(output, mimetype='text/html')
                else:
                    response = response_class(output, mimetype='text/plain')

                return response
            else:
                '''Add the dictionary to the context and let
                render_to_response handle it'''
                request.context.update(response)
                response = None
                pop = True

        if isinstance(response, http.HttpResponse):
            return response

        elif isinstance(response, basestring):
            if request.ajax:
                return response_class(response, mimetype='text/plain')
            else:
                return response_class(response)

        elif response is None:
            if request.jinja:
                assert coffin_shortcuts, ('To use Jinja the `coffin` module '
                    'must be installed')
                render_to_string = coffin_shortcuts.render_to_string
            else:
                render_to_string = django_loader.render_to_string

            return response_class(render_to_string(
                request.template, context_instance=request.context))

        else:
            raise UnknownViewResponseError(
                '"%s" is an unsupported response type' % type(response))
    finally:
        if pop:
            request.context.pop()


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
        request.ajax = request.is_ajax() or bool(int(
            request.REQUEST.get('ajax', 0)))
        request.context = None
        request.jinja = getattr(settings, 'DJANGO_UTILS_USE_JINJA', False)
        try:
            name = function.__name__
            app = function.__module__.split('.')[0]
            request = _prepare_request(request, app, name)
            request.template = '%s/%s.html' % (app, name)
            response = function(request, *args, **kwargs)

            return _process_response(request, response, response_class)
        finally:
            '''Remove the context reference from request to prevent leaking'''
            try:
                del request.context, request.template
                for k, v in REQUEST_PROPERTIES.iteritems():
                    delattr(request, k)
            except AttributeError:
                pass

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
        return lambda f: env(f, login_required, response_class)
