import json
from django import http


def to_json(request, data):
    if request.GET.get('debug'):  # pragma: no cover
        response = json.dumps(data, indent=4)
        try:
            from pygments import highlight, lexers, formatters
            return http.HttpResponse(highlight(
                response,
                lexers.get_lexer_by_name('json'),
                formatters.get_formatter_by_name('html', full=True),
            ))
        except ImportError:
            return http.HttpResponse(response, content_type='text/plain')
    else:
        return http.HttpResponse(
            json.dumps(data), content_type='application/json')

