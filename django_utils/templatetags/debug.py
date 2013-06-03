from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.db import models
import copy
import pprint

register = template.Library()

def dump(value):
    dict_ = getattr(value, '__dict__', None)
    if not dict_:
        dict_ = {}
        for k in dir(value):
            v = getattr(value, k, None)
            if v is not None:
                dict_[k] = v

    for k in dict_.keys():
        if k.startswith('__'):
            dict_.pop(k)

    return dict_

class _Formatter(object):
    formatters_type = {}
    formatters_instance = []

class Formatter(_Formatter):
    def __init__(self, max_depth=3):
        self.max_depth = 3

    def register(*types):
        def _register(func):
            for type_ in types:
                _Formatter.formatters_type[type_] = func
                _Formatter.formatters_instance.append((type_, func))

            return func

        return _register

    @register(str)
    def format_str(self, value, depth):
        return self.format_unicode(unicode(value, 'utf-8', 'replace'))

    @register(unicode)
    def format_unicode(self, value, depth):
        if value[100:]:
            value = value[:97] + '...'
        return value

    @register(list)
    def format_list(self, value, depth):
        for i, v in enumerate(value):
            value[i] = self(v, depth-1)
        return value

    @register(dict)
    def format_dict(self, value, depth):
        for k, v in value.items():
            value[k] = self(v, depth-1)
        return value

    @register(models.Model)
    def format_model(self, value, depth):
        return self.format_dict(value.__dict__, depth)

    def __call__(self, value, depth=None):
        # Specific is None check since we don't want to replace 0
        if depth is None:
            depth = self.max_depth

        formatter = self.formatters_type.get(type(value))
        if not formatter:
            for k, v in self.formatters_instance:
                if isinstance(value, k):
                    formatter = v
                    break

        if not formatter:
            formatter = lambda self, v, depth: pprint.pformat(v)

        return formatter(self, value, depth)

@register.filter
def debug(value, max_depth=3):
    value = copy.deepcopy(value)
    formatter = Formatter(max_depth=max_depth)
    formatted_safe = mark_safe('''
    <pre style="border: 1px solid #fcc; background-color: #ccc;">%s</pre>
    ''' % conditional_escape(pprint.pformat(formatter(value))))
    return formatted_safe

