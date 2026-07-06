from django.core import exceptions


def error_403(request):
    raise exceptions.PermissionDenied


def error_500(request):
    # Zero division error
    _ = 1 / 0
