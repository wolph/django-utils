from django import http

from . import view_decorators


@view_decorators.env(response_class=http.HttpResponseForbidden)
def error_403(request: http.HttpRequest, exception: Exception) -> None:
    pass


@view_decorators.env(response_class=http.HttpResponseNotFound)
def error_404(request: http.HttpRequest, exception: Exception) -> None:
    pass


@view_decorators.env(response_class=http.HttpResponseServerError)
def error_500(request: http.HttpRequest) -> None:
    pass
