import sys
print sys.path
import anyjson
from django import shortcuts as django_shortcuts
from django import http
from django.template import RequestContext
from django.contrib.auth import decorators


class ViewError(Exception):
    pass


class UnknownViewResponseError(ViewError):
    pass

REQUEST_PROPERTIES = {
    'redirect': http.HttpResponseRedirect,
    'permanent_redirect': http.HttpResponsePermanentRedirect,
    'not_found': http.HttpResponseNotFound,
}


def _prepare_request(request, app, view):
    '''Add context and extra methods to the request'''
    request.context = RequestContext(request)
    request.context['view'] = view
    request.context['app'] = app

    for k, v in REQUEST_PROPERTIES.iteritems():
        setattr(request, k, v)

    return request


def _process_response(request, response):
    '''Generic response processing function, always returns HttpResponse'''

    '''If we add something to the context stack, pop it after adding'''
    pop = False

    try:
        if isinstance(response, (dict, list)):
            if request.ajax:
                output = json = anyjson.serialize(response)
                callback = request.GET.get('callback', False)
                if callback:
                    output = '%s(%s)' % (callback, json)
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
                    response = http.HttpResponse(output,
                        mimetype='text/html')
                else:
                    response = http.HttpResponse(output,
                        mimetype='text/plain')

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
                return http.HttpResponse(response, mimetype='text/plain')
            else:
                return http.HttpResponse(response)

        elif response is None:
            render_to_response = django_shortcuts.render_to_response

            return render_to_response(request.template,
                context_instance=request.context)

        else:
            raise UnknownViewResponseError(
                '"%s" is an unsupported response type' % type(response))
    finally:
        if pop:
            request.context.pop()


def env(function=None, login_required=False):
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
        try:
            name = function.__name__
            app = function.__module__.split('.')[0]

            request = _prepare_request(request, app, name)

            if app:
                request.template = '%s/%s.html' % (app, name)
            else:
                request.template = '%s.html' % name

            response = function(request, *args, **kwargs)

            return _process_response(request, response)
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
        return lambda f: env(f, login_required)

