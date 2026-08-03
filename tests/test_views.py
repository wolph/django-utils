import contextlib

from django.test import TestCase, client


class TestCalls(TestCase):
    def setUp(self):
        self.client = client.Client()

    def test_400(self):
        response = self.client.get('/error_400')
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, '400', status_code=400)

    def test_403(self):
        self.client.get('/error_403')

    def test_404(self):
        self.client.get('/error_404')

    def test_500(self):
        with contextlib.suppress(ZeroDivisionError):
            self.client.get('/error_500')
