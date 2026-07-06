import contextlib
import datetime
import sys

import pytest
from django import http, template
from django.contrib.auth import models as auth_models
from django.contrib.contenttypes import models
from django_utils import utils, view_decorators


class Request:
    def __init__(self, ajax=False):
        self.user = auth_models.AnonymousUser()
        self.headers = {'x-requested-with': 'XMLHttpRequest'} if ajax else {}
        self.REQUEST = dict()
        self.POST = dict()
        self.GET = dict()

    def build_absolute_uri(self):
        return '/'

    def get_full_path(self):
        return '/'


def test_to_json():
    request = Request()
    utils.to_json(request, {})
    request.GET['debug'] = True
    utils.to_json(request, {})


@view_decorators.env()
def simple_view(request):
    return ''


@view_decorators.env(login_required=True)
def simple_logged_in_view(request):
    return ''


def test_other_view():
    request = Request(ajax=True)
    simple_logged_in_view(request)
    simple_view(request)


@view_decorators.env
def some_view(request, return_=None):
    request.redirect('/')
    request.permanent_redirect('/')
    request.redirect('admin:index')
    request.permanent_redirect('admin:index')

    del request.redirect

    return return_


@pytest.mark.django_db()
def test_some_view():
    some_view(Request(), return_='')
    some_view(Request(ajax=True), return_='')
    some_view(Request(ajax=True), return_={})
    some_view(
        Request(ajax=True),
        return_=models.ContentType.objects.all(),
    )
    request = Request(ajax=True)
    request.GET['callback'] = 'call_me'
    request.GET['debug'] = 'debug'
    some_view(
        request,
        return_={
            'now': datetime.datetime.now(),
        },
    )

    with contextlib.suppress(TypeError):
        some_view(
            request,
            return_={
                'request': request,
            },
        )

    with contextlib.suppress(template.TemplateDoesNotExist):
        some_view(Request(), return_=[])

    with contextlib.suppress(view_decorators.UnknownViewResponseError):
        some_view(Request(), return_=request)

    some_view(request, return_=http.HttpResponse())
    some_view(request)


def test_import():
    import builtins

    removed_modules = {}
    for name in list(sys.modules.keys()):
        if name.startswith('django_utils'):
            removed_modules[name] = sys.modules.pop(name)

    original_import = builtins.__import__

    builtins.__import__ = original_import

    for name, module in removed_modules.items():
        sys.modules[name] = module
