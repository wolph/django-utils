import json
from typing import Any

from django import http
from django.core.serializers.json import DjangoJSONEncoder


def to_json(request: http.HttpRequest, data: Any) -> http.HttpResponse:
    if request.GET.get('debug'):  # pragma: no cover
        response = json.dumps(data, indent=4, cls=DjangoJSONEncoder)
        try:
            from pygments import formatters, highlight, lexers

            return http.HttpResponse(
                highlight(
                    response,
                    lexers.get_lexer_by_name('json'),
                    formatters.get_formatter_by_name('html', full=True),
                )
            )
        except ImportError:
            return http.HttpResponse(response, content_type='text/plain')
    else:
        return http.HttpResponse(
            json.dumps(data, cls=DjangoJSONEncoder),
            content_type='application/json',
        )
