from django.test import client, TestCase
from django.test.client import RequestFactory

from django.core import urlresolvers


class TestCalls(TestCase):
    def setUp(self):
        self.client = client.Client()

    def test_400(self):
        resolver = urlresolvers.get_resolver(urlresolvers.get_urlconf())
        view, _ = resolver.resolve400()
        factory = client.RequestFactory()
        view(factory.get('/error_400'))

    def test_403(self):
        self.client.get('/error_403')

    def test_404(self):
        self.client.get('/error_404')

    def test_500(self):
        try:
            self.client.get('/error_500')
        except ZeroDivisionError:
            pass

