from django.test import client, TestCase


class TestCalls(TestCase):

    def setUp(self):
        self.client = client.Client()

    def test_403(self):
        self.client.get('/error_403')

    def test_404(self):
        self.client.get('/error_404')

    def test_500(self):
        try:
            self.client.get('/error_500')
        except ZeroDivisionError:
            pass
