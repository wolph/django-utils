import typing

from django import http
from django.core import exceptions


def error_400(request: http.HttpRequest) -> typing.NoReturn:
    raise exceptions.SuspiciousOperation


def error_403(request):
    raise exceptions.PermissionDenied


def error_500(request):
    # Zero division error
    _ = 1 / 0
