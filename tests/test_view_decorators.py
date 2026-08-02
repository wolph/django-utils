import contextlib
import datetime

import pytest
from django import http, template
from django.contrib.auth import models as auth_models
from django.contrib.contenttypes import models
from django.core.exceptions import SuspiciousOperation
from django.test import RequestFactory, override_settings
from django_utils import utils, view_decorators


class Request:
    def __init__(self, ajax=False):
        self.user = auth_models.AnonymousUser()
        self.headers = {'x-requested-with': 'XMLHttpRequest'} if ajax else {}
        self.REQUEST = dict()
        self.POST = dict()
        self.GET = dict()
        self.META = dict()

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


@view_decorators.env
def _payload_view(request):
    return {'ok': True, 'name': '</textarea><script>alert(1)</script>'}


BREAKOUT = '</textarea><script>alert(1)</script>'


@override_settings(DEBUG=True)
def test_debug_html_escapes_the_response_body():
    request = RequestFactory().get('/x/', {'ajax': '1', 'debug': '1'})
    body = _payload_view(request).content.decode()
    assert BREAKOUT not in body
    assert '&lt;/textarea&gt;' in body


@override_settings(DEBUG=True)
def test_debug_html_escapes_the_title():
    request = RequestFactory().get(
        '/x/', {'ajax': '1', 'debug': '1', 'q': '</title><script>x</script>'}
    )
    body = _payload_view(request).content.decode()
    assert '</title><script>' not in body


@override_settings(DEBUG=False, INTERNAL_IPS=[])
def test_debug_html_refused_in_production():
    request = RequestFactory().get('/x/', {'ajax': '1', 'debug': '1'})
    response = _payload_view(request)
    assert response['Content-Type'] == 'text/plain'
    assert '<textarea>' not in response.content.decode()


@override_settings(DEBUG=False, INTERNAL_IPS=['127.0.0.1'])
def test_debug_html_allowed_for_internal_ip():
    # RequestFactory sets REMOTE_ADDR to 127.0.0.1
    request = RequestFactory().get('/x/', {'ajax': '1', 'debug': '1'})
    response = _payload_view(request)
    assert response['Content-Type'] == 'text/html'
    assert '<textarea>' in response.content.decode()


@override_settings(DEBUG=True)
def test_jsonp_callback_must_be_an_identifier():
    request = RequestFactory().get(
        '/x/',
        {'ajax': '1', 'callback': '</textarea><script>alert(1)</script>'},
    )
    with pytest.raises(SuspiciousOperation):
        _payload_view(request)


@override_settings(DEBUG=True)
def test_jsonp_callback_accepts_a_valid_identifier():
    request = RequestFactory().get('/x/', {'ajax': '1', 'callback': 'myFunc'})
    body = _payload_view(request).content.decode()
    assert body.startswith('myFunc(')
