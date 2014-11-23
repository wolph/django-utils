from django import template
from django.utils.html import conditional_escape
from django.utils.safestring import mark_safe
from django.db import models
import six
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

    @_register(*six.integer_types)
    def format_int(self, value, depth, show_protected, show_special):
        '''Format an integer/long

        :param value: an int/long to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> str(formatter(1, 0))
        '1'
        >>> formatter(1, 1)
        '1'
        '''
        return value

    @_register(six.binary_type)
    def format_str(self, value, depth, show_protected, show_special):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> str(formatter('test'))
        'test'
        >>> str(formatter(six.b('test')))
        'test'
        '''
        return self.format_unicode(value.decode('utf-8', 'replace'), depth,
                                   show_protected, show_special)

    @_register(six.text_type)
    def format_unicode(self, value, depth, show_protected, show_special):
        '''Format a string

        :param value: a unicode value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> original_max_length = formatter.MAX_LENGTH
        >>> formatter.MAX_LENGTH = 10
        >>> str(formatter('x' * 11))
        'xxxxxxx...'
        >>> formatter.MAX_LENGTH = original_max_length
        '''
        if value[self.MAX_LENGTH:]:
            value = value[:self.MAX_LENGTH - self.MAX_LENGTH_DOTS]
            value += self.MAX_LENGTH_DOTS * '.'
        return value

    @_register(list)
    def format_list(self, value, depth, show_protected, show_special):
        '''Format a string

        :param value: a list to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(list(range(5)))
        '[0, 1, 2, 3, 4]'
        '''
        values = []
        for i, v in enumerate(value):
            values.append(self.format(v, depth - 1, show_protected,
                                      show_special))

        return values

    @_register(datetime.datetime, datetime.date)
    def format_datetime(self, value, depth, show_protected, show_special):
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
    def format_dict(self, value, depth, show_protected, show_special):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter({'a': 1, 'b': 2}, 5)
        '{a: 1, b: 2}'
        '''
        def key(key):
            '''Make sure that hidden/protected variables end up at the end'''
            key = key[0]
            if 'a' <= key[0].lower() <= 'z' or '0' <= key[0] <= '9':
                return 0, key
            else:
                return 1, key

        output = []
        for k, v in sorted(value.items(), key=key):
            output.append('%s: %s' % (
                k, self(v, depth - 1, show_protected, show_special)))

        return '{%s}' % self.format_unicode(
            ', '.join(output), depth - 1, show_protected, show_special)

    @_register(models.Model)
    def format_model(self, value, depth, show_protected, show_special):
        '''Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> from django.contrib.auth.models import User
        >>> user = User()
        >>> del user.date_joined
        >>> str(formatter(user, 5, show_protected=False)[:30])
        '<User {email: , first_name: , '
        '''
        return self.format_object(value, depth, False, False)

    def format_object(self, value, depth, show_protected, show_special):
        '''Format an object

        :param value: an object to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> original_max_length = formatter.MAX_LENGTH
        >>> formatter.MAX_LENGTH = 50

        >>> class Spam(object):
        ...     x = 1
        ...     _y = 2
        ...     __z = 3
        ...     __hidden_ = 4
        >>> spam = Spam()

        >>> str(formatter(spam, show_protected=True, show_special=True))
        '<Spam {x: 1, _Spam__hidden_: 4, _Spam__z: 3, __dict__:...}>'
        >>> str(formatter(spam, show_protected=False, show_special=False))
        '<Spam {x: 1}>'

        >>> formatter.MAX_LENGTH = original_max_length
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

        for k in list(dict_.keys()):
            if k.startswith('__'):
                if not show_special:
                    dict_.pop(k)
            elif k.startswith('_') and not show_protected:
                dict_.pop(k)

        # Difference between Python 2 and 3, the results are covered by tests
        # regardless so the no cover is not important :)
        if hasattr(value, '__name__'):  # pragma: no cover
            name = value.__name__
        elif(hasattr(value, '__class__') and
                hasattr(value.__class__, '__name__')):  # pragma: no cover
            name = value.__class__.__name__
        else:  # pragma: no cover
            module = __name__
            name = str(value).replace(module + '.', '', 1)

        return '<%s %s>' % (
            name,
            self.format(dict_, depth - 1, show_protected, show_special),
        )

    def format(self, value, depth, show_protected, show_special):
        '''Call the formatter with the given value to format and optional depth

        >>> formatter = Formatter()
        >>> class Eggs: pass
        >>> formatter(Eggs)
        '<Eggs {}>'
        '''
        # Specific "is None" check since we don't want to replace 0
        if depth is None:
            depth = self.max_depth
        elif depth <= 0:
            return self.format_unicode(six.text_type(value), depth - 1,
                                       show_protected, show_special)

        formatter = self.formatters_type.get(type(value))

        if not formatter:
            for k, v in self.formatters_instance:
                if isinstance(value, k):
                    formatter = v
                    break

        if not formatter:
            formatter = Formatter.format_object

        return formatter(self, value, depth, show_protected, show_special)

    def __call__(self, value, depth=None, show_protected=True,
                 show_special=False):
        formatted = self.format(value, depth, show_protected, show_special)
        if not isinstance(formatted, six.string_types):
            formatted = pprint.pformat(formatted)

        return formatted


@register.filter
def debug(value, max_depth=3):
    '''Debug template filter to print variables in a pretty way

    >>> str(debug(123).strip())
    '<pre style="border: 1px solid #fcc; background-color: #ccc;">123</pre>'
    '''
    value = copy.deepcopy(value)
    formatter = Formatter(max_depth=max_depth)
    formatted_safe = mark_safe('''
    <pre style="border: 1px solid #fcc; background-color: #ccc;">%s</pre>
    ''' % conditional_escape(formatter(value)))
    return formatted_safe
