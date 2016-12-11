import sys
import pytest
import datetime

from django import template
from django import http
from django.contrib.contenttypes import models
from django.contrib.auth import models as auth_models

from django_utils import view_decorators
from django_utils import utils


class Request(object):

    def __init__(self, ajax=False):
        self.ajax = ajax
        self.user = auth_models.AnonymousUser()
        self.REQUEST = dict()
        self.POST = dict()
        self.GET = dict()

    def build_absolute_uri(self):
        return '/'

    def get_full_path(self):
        return '/'

    def is_ajax(self):
        return self.ajax


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
    some_view(Request(
        ajax=True),
        return_=models.ContentType.objects.all(),
    )
    request = Request(ajax=True)
    request.GET['callback'] = 'call_me'
    request.GET['debug'] = 'debug'
    some_view(request, return_={
        'now': datetime.datetime.now(),
    })

    try:
        some_view(request, return_={
            'request': request,
        })
    except TypeError:
        pass

    try:
        some_view(Request(), return_=[])
    except template.TemplateDoesNotExist:
        pass

    try:
        some_view(Request(), return_=request)
    except view_decorators.UnknownViewResponseError:
        pass

    some_view(request, return_=http.HttpResponse())
    some_view(request)


def test_import():
    if sys.version_info[0] == 2:
        import __builtin__ as builtins
    else:
        import builtins

    removed_modules = {}
    for name in list(sys.modules.keys()):
        if name.startswith('django_utils'):
            removed_modules[name] = sys.modules.pop(name)

    original_import = builtins.__import__

    builtins.__import__ = original_import

    for name, module in removed_modules.items():
        sys.modules[name] = module
