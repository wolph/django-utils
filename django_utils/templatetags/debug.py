from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.db import models
import copy
import pprint
import datetime

register = template.Library()


class _Formatter(object):
    formatters_type = {}
    formatters_instance = []


class Formatter(_Formatter):
    MAX_LENGTH = 100
    MAX_LENGTH_DOTS = 3

    def __init__(self, max_depth=3):
        '''Initialize the formatter with a given maximum default depth

        :param max_depth: The maximum depth to print
        '''
        self.max_depth = max_depth

    def _register(*types):
        '''Register a handler for the given type(s)

        :param types: The type(s) to handle
        :return: The unmodified decorated function
        '''
        def _register(func):
            for type_ in types:
                _Formatter.formatters_type[type_] = func
                _Formatter.formatters_instance.append((type_, func))

            return func

        return _register

    @_register(str)
    def format_str(self, value, depth):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter('test')
        u'test'
        '''
        return self.format_unicode(unicode(value, 'utf-8', 'replace'), depth)

    @_register(int, long)
    def format_int(self, value, depth):
        '''Format an integer/long

        :param value: an int/long to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(1, 1)
        1
        >>> formatter(2L, 1)
        2L
        '''
        return value

    @_register(unicode)
    def format_unicode(self, value, depth):
        '''Format a string

        :param value: a unicode value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> old_max_length = formatter.MAX_LENGTH
        >>> formatter.MAX_LENGTH = 10
        >>> formatter('x' * 11)
        u'xxxxxxx...'
        >>> formatter.MAX_LENGTH = old_max_length
        '''
        if value[self.MAX_LENGTH:]:
            value = value[:self.MAX_LENGTH - self.MAX_LENGTH_DOTS]
            value += self.MAX_LENGTH_DOTS * '.'
        return value

    @_register(list)
    def format_list(self, value, depth):
        '''Format a string

        :param value: a list to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(range(5))
        [0, 1, 2, 3, 4]
        '''
        values = []
        for i, v in enumerate(value):
            values.append(self(v, depth - 1))
        return values

    @_register(datetime.datetime, datetime.date)
    def format_datetime(self, value, depth):
        '''Format a date

        :param value: a date to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(datetime.date(2000, 1, 2))
        '<date:2000-01-02>'
        >>> formatter(datetime.datetime(2000, 1, 2, 3, 4, 5, 6))
        '<datetime:2000-01-02 03:04:05.000006>'
        '''
        return '<%s:%s>' % (
            value.__class__.__name__,
            value,
        )

    @_register(dict)
    def format_dict(self, value, depth):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter({'a': 1, 'b': 2}, 5)
        {'a': 1, 'b': 2}
        '''
        for k, v in value.items():
            value[k] = self(v, depth - 1)
        return value

    @_register(models.Model)
    def format_model(self, value, depth):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> from django.contrib.auth.models import User
        >>> user = User()
        >>> str(formatter(user, 5))[:30]
        "{'username': u'', 'first_name'"
        '''
        return self.format_dict(value.__dict__, depth)

    def format_object(self, value, depth):
        '''Format an object

        :param value: an object to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> class Spam(object):
        ...     x = 1
        ...     y = 2
        >>> spam = Spam()
        >>> formatter(spam, 1)
        ('<Spam', {'x': u'1', 'y': u'2'}, '>')
        '''
        dict_ = getattr(value, '__dict__', None)
        if dict_:
            dict_ = dict(dict_)
        else:
            dict_ = {}
            for k in dir(value):
                v = getattr(value, k, None)
                if v is not None and not hasattr(v, '__call__'):
                    dict_[k] = v

        for k in dict_.keys():
            if k.startswith('__'):
                dict_.pop(k)

        for k, v in dict_.items():
            dict_[k] = self(v, depth - 1)

        if(hasattr(value, '__class__') and
                hasattr(value.__class__, '__name__')):
            name = value.__class__.__name__
        else:
            module = __name__
            name = str(value).replace(module + '.', '', 1)

        # return dict_
        return (
            '<%s' % name,
            dict_,
            '>',
        )

    def __call__(self, value, depth=None):
        '''Call the formatter with the given value to format and optional depth

        >>> formatter = Formatter()
        >>> class Eggs: pass
        >>> formatter(Eggs)
        ('<Eggs', {}, '>')
        '''
        # Specific is None check since we don't want to replace 0
        if depth is None:
            depth = self.max_depth
        elif depth <= 0:
            return self.format_unicode(unicode(value), depth - 1)

        formatter = self.formatters_type.get(type(value))
        # print 'value: %s, type: %s, formatter: %s' % (
        #     value,
        #     type(value),
        #     formatter,
        # )

        if not formatter:
            for k, v in self.formatters_instance:
                if isinstance(value, k):
                    formatter = v
                    break

        if not formatter:
            formatter = Formatter.format_object
                # formatter = lambda self, v, depth: pprint.pformat(v)

        return formatter(self, value, depth)


@register.filter
def debug(value, max_depth=3):
    '''Debug template filter to print variables in a pretty way

    >>> debug(123).strip()
    u'<pre style="border: 1px solid #fcc; background-color: #ccc;">123</pre>'
    '''
    value = copy.deepcopy(value)
    formatter = Formatter(max_depth=max_depth)
    formatted_safe = mark_safe('''
    <pre style="border: 1px solid #fcc; background-color: #ccc;">%s</pre>
    ''' % conditional_escape(pprint.pformat(formatter(value))))
    return formatted_safe
