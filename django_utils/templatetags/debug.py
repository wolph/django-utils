import copy
import datetime
import pprint
import typing
from collections.abc import Callable
from typing import Any, ClassVar, TypeVar

from django import template
from django.conf import settings
from django.db import models
from django.utils.html import conditional_escape
from django.utils.safestring import SafeString, mark_safe

register = template.Library()

_F = TypeVar('_F', bound=Callable[..., Any])

# The formatter methods are stored unbound and invoked as
# ``formatter(self, value, depth, show_protected, show_special)``.
FormatterFunction = Callable[['Formatter', Any, int, bool, bool], Any]


class _Formatter:
    formatters_type: ClassVar[dict[type, FormatterFunction]] = {}
    formatters_instance: ClassVar[list[tuple[type, FormatterFunction]]] = []


def _register(*types: type) -> Callable[[_F], _F]:
    """Register a handler for the given type(s)

    :param types: The type(s) to handle
    :return: The unmodified decorated function
    """

    def _register_inner(func: _F) -> _F:
        for type_ in types:
            _Formatter.formatters_type[type_] = typing.cast(
                FormatterFunction, func
            )
            _Formatter.formatters_instance.append(
                (type_, typing.cast(FormatterFunction, func))
            )

        return func

    return _register_inner


class Formatter(_Formatter):
    MAX_LENGTH = 100
    MAX_LENGTH_DOTS = 3

    def __init__(self, max_depth: int = 3) -> None:
        """Initialize the formatter with a given maximum default depth

        :param max_depth: The maximum depth to print
        """
        self.max_depth = max_depth

    @_register(int)
    def format_int(
        self,
        value: int,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> Any:
        """Format an integer/long

        :param value: an int/long to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> str(formatter(1, 0))
        '1'
        >>> formatter(1, 1)
        '1'
        """
        return value

    @_register(bytes)
    def format_str(
        self,
        value: bytes,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> Any:
        """Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> str(formatter('test'))
        'test'
        >>> str(formatter(b'test'))
        'test'
        """
        return self.format_unicode(
            value.decode('utf-8', 'replace'),
            depth,
            show_protected,
            show_special,
        )

    @_register(str)
    def format_unicode(
        self,
        value: str,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> str:
        """Format a string

        :param value: a unicode value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> original_max_length = formatter.MAX_LENGTH
        >>> formatter.MAX_LENGTH = 10
        >>> str(formatter('x' * 11))
        'xxxxxxx...'
        >>> formatter.MAX_LENGTH = original_max_length
        """
        if value[self.MAX_LENGTH :]:
            value = value[: self.MAX_LENGTH - self.MAX_LENGTH_DOTS]
            value += self.MAX_LENGTH_DOTS * '.'
        return value

    @_register(list)
    def format_list(
        self,
        value: list[Any],
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> list[Any]:
        """Format a string

        :param value: a list to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(list(range(5)))
        '[0, 1, 2, 3, 4]'
        """
        return [
            self.format(v, depth - 1, show_protected, show_special)
            for v in value
        ]

    @_register(datetime.datetime, datetime.date)
    def format_datetime(
        self,
        value: datetime.date,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> str:
        """Format a date

        :param value: a date to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter(datetime.date(2000, 1, 2))
        '<date:2000-01-02>'
        >>> formatter(datetime.datetime(2000, 1, 2, 3, 4, 5, 6))
        '<datetime:2000-01-02 03:04:05.000006>'
        """
        return f'<{value.__class__.__name__}:{value}>'

    @_register(dict)
    def format_dict(
        self,
        value: dict[Any, Any],
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> str:
        """Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> formatter({'a': 1, 'b': 2}, 5)
        '{a: 1, b: 2}'
        """

        def key(item: tuple[Any, Any]) -> tuple[int, Any]:
            """Make sure that hidden/protected variables end up at the end"""
            k = item[0]
            if 'a' <= k[0].lower() <= 'z' or '0' <= k[0] <= '9':
                return 0, k
            else:
                return 1, k

        output: list[str] = []
        for k, v in sorted(value.items(), key=key):
            formatted = self(v, depth - 1, show_protected, show_special)
            output.append(f'{k}: {formatted}')

        formatted = self.format_unicode(
            ', '.join(output), depth - 1, show_protected, show_special
        )
        return f'{{{formatted}}}'

    @_register(models.Model)
    def format_model(
        self,
        value: models.Model,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> Any:
        """Format a string

        :param value: a str value to format
        :param depth: the current depth
        :return: a formatted string

        >>> formatter = Formatter()
        >>> from django.contrib.auth.models import User
        >>> user = User()
        >>> del user.date_joined
        >>> str(formatter(user, 5, show_protected=False)[:30])
        '<User {email: , first_name: , '
        """
        return self.format_object(value, depth, False, False)

    def format_object(
        self,
        value: Any,
        depth: int,
        show_protected: bool,
        show_special: bool,
    ) -> str:
        """Format an object

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

        >>> str(formatter(spam, show_protected=False, show_special=False))
        '<Spam {x: 1}>'
        >>> str(formatter(spam, show_protected=True, show_special=True))
        '<Spam {x: 1, _Spam__hidden_: 4, _Spam__z: 3, __dict__:...}>'

        >>> formatter.MAX_LENGTH = original_max_length
        """
        dict_ = getattr(value, '__dict__', None)
        if dict_:
            dict_ = dict(dict_)
        else:
            dict_ = {}
            for k in dir(value):
                v = getattr(value, k, None)
                if v is not None and not callable(v):
                    dict_[k] = v

        for k in list(dict_.keys()):
            if k.startswith('__'):
                if not show_special:
                    dict_.pop(k)
            elif k.startswith('_') and not show_protected:
                dict_.pop(k)

        if hasattr(value, '__name__'):  # pragma: no cover
            name = value.__name__
        elif getattr(getattr(value, '__class__', None), '__name__', None):
            name = value.__class__.__name__
        else:  # pragma: no cover
            module = __name__
            name = str(value).replace(module + '.', '', 1)

        formatted = self.format(dict_, depth - 1, show_protected, show_special)
        return f'<{name} {formatted}>'

    def format(
        self,
        value: Any,
        depth: int | None,
        show_protected: bool,
        show_special: bool,
    ) -> Any:
        """Call the formatter with the given value to format and optional depth

        >>> formatter = Formatter()
        >>> class Eggs:
        ...     pass
        >>> formatter(Eggs)
        '<Eggs {}>'
        """
        # Specific "is None" check since we don't want to replace 0
        if depth is None:
            depth = self.max_depth
        elif depth <= 0:
            return self.format_unicode(
                str(value), depth - 1, show_protected, show_special
            )

        formatter: FormatterFunction | None = self.formatters_type.get(
            type(value)
        )

        if not formatter:
            for k, v in self.formatters_instance:
                if isinstance(value, k):
                    formatter = v
                    break

        if not formatter:
            formatter = Formatter.format_object

        return formatter(self, value, depth, show_protected, show_special)

    def __call__(
        self,
        value: Any,
        depth: int | None = None,
        show_protected: bool = True,
        show_special: bool = False,
    ) -> str:
        formatted = self.format(value, depth, show_protected, show_special)
        if not isinstance(formatted, str):
            formatted = pprint.pformat(formatted)

        return formatted


@register.filter
def debug(value: Any, max_depth: int = 3) -> SafeString:
    """Debug template filter to print variables in a pretty way

    Returns an empty string unless ``settings.DEBUG`` is enabled, so a
    filter left in a shipped template cannot leak internal state. This
    mirrors Django's own ``{% debug %}`` tag.

    >>> from django.test import override_settings
    >>> with override_settings(DEBUG=True):
    ...     str(debug(123).strip())
    '<pre style="border: 1px solid #fcc; background-color: #ccc;">123</pre>'
    >>> with override_settings(DEBUG=False):
    ...     str(debug(123).strip())
    ''
    """
    if not settings.DEBUG:
        return mark_safe('')

    value = copy.deepcopy(value)
    formatter = Formatter(max_depth=max_depth)
    return mark_safe(
        f"""
    <pre style="border: 1px solid #fcc; background-color: #ccc;">{
            conditional_escape(formatter(value, show_protected=False))
        }</pre>
    """
    )
