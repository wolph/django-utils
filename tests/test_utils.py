import datetime
import decimal
import json
import uuid

from django.test import RequestFactory
from django_utils import utils


def test_to_json_serialises_django_native_types():
    data = {
        'when': datetime.datetime(2026, 1, 2, 3, 4, 5),
        'day': datetime.date(2026, 1, 2),
        'amount': decimal.Decimal('1.25'),
        'id': uuid.UUID('12345678-1234-5678-1234-567812345678'),
    }
    response = utils.to_json(RequestFactory().get('/'), data)
    payload = json.loads(response.content)

    assert payload['when'].startswith('2026-01-02')
    assert payload['day'] == '2026-01-02'
    assert payload['amount'] == '1.25'
    assert payload['id'] == '12345678-1234-5678-1234-567812345678'


def test_to_json_sets_the_json_content_type():
    response = utils.to_json(RequestFactory().get('/'), {'a': 1})
    assert response['Content-Type'] == 'application/json'
