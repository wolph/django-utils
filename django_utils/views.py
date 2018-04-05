from . import view_decorators
from django import http


@view_decorators.env(response_class=http.HttpResponseForbidden)
def error_403(request, exception):
    pass


@view_decorators.env(response_class=http.HttpResponseNotFound)
def error_404(request, exception):
    pass


@view_decorators.env(response_class=http.HttpResponseServerError)
def error_500(request):
    pass
