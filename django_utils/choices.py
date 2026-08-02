"""
Usage
------------------------------------------------------------------------------

Create a :py:class:`Choices` class and add :py:class:`Choice` objects to the
class to define your choices.

Example with explicit values:
==============================================================================

The normal Django version:

.. code-block:: python

    class Human(models.Model):
        GENDER = (
            ('m', 'Male'),
            ('f', 'Female'),
            ('o', 'Other'),
        )
        gender = models.CharField(max_length=1, choices=GENDER)

The Django Utils Choices version:

.. code-block:: python

    from django_utils import choices


    class Human(models.Model):
        class Gender(choices.Choices):
            Male = choices.Choice('m')
            Female = choices.Choice('f')
            Other = choices.Choice('o')

        gender = models.CharField(max_length=1, choices=Gender)

To reference these properties:

.. code-block:: python

    Human.create(gender=Human.Gender.Male)

Example with implicit values:
==============================================================================

The normal Django version:

.. code-block:: python

    class SomeModel(models.Model):
        SOME_ENUM = (
            (1, 'foo'),
            (2, 'bar'),
            (3, 'spam'),
            (4, 'eggs'),
        )
        enum = models.IntegerField(choices=SOME_ENUM, default=1)

The Django Utils Choices version:

.. code-block:: python

    from django_utils import choices


    class SomeModel(models.Model):
        class Enum(choices.Choices):
            Foo = choices.Choice()
            Bar = choices.Choice()
            Spam = choices.Choice()
            Eggs = choices.Choice()

        enum = models.IntegerField(choices=Enum, default=Enum.Foo)

To reference these properties:

.. code-block:: python

    SomeModel.create(enum=SomeModel.Enum.Spam)

Excluding constants
==============================================================================

Any plain ``str``, ``int`` or ``float`` class attribute becomes a choice.
To keep a constant alongside your choices, list it in ``_ignore_``:

.. code-block:: python

    class Gender(choices.Choices):
        _ignore_ = ('MAX_LENGTH',)
        MAX_LENGTH = 1

        Male = choices.Choice('m')
        Female = choices.Choice('f')

Like the standard library's ``enum``, ``_ignore_`` also accepts a single
string of names separated by whitespace and/or commas, which is split for
you:

.. code-block:: python

    class Gender(choices.Choices):
        _ignore_ = 'MAX_LENGTH'
        MAX_LENGTH = 1

        Male = choices.Choice('m')
        Female = choices.Choice('f')

Attaching metadata to choices
==============================================================================

Unlike Django's ``TextChoices``, a :py:class:`Choice` can carry arbitrary
extra data, reachable as attributes:

.. code-block:: python

    class Status(choices.Choices):
        Active = choices.Choice('a', 'Active', color='green')
        Closed = choices.Choice('c', 'Closed', color='red')


    Status.choices['a'].color  # 'green'

"""

import collections
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.utils.functional import Promise as StrPromise


class ChoicesDict:
    """The choices dict is an object that stores a sorted representation of
    the values by key and database value"""

    def __init__(self) -> None:
        self._by_value: collections.OrderedDict[Any, Choice] = (
            collections.OrderedDict()
        )
        self._by_key: collections.OrderedDict[str, Choice] = (
            collections.OrderedDict()
        )

        # Reset the choice creation counter since this will only be accessed
        # after processing the choices
        Choice.order = 0

    def __getitem__(self, key: Any) -> 'Choice':
        if key in self._by_value:
            return self._by_value[key]
        elif key in self._by_key:
            return self._by_key[key]
        else:
            raise KeyError(f'Key {key!r} does not exist')

    def __setitem__(self, key: str, value: 'Choice') -> None:
        self._by_key[key] = value
        self._by_value[value.value] = value

    def __iter__(self) -> Iterator[tuple[Any, 'Choice']]:
        yield from self._by_value.items()

    def items(self) -> list[tuple[Any, 'Choice']]:
        return list(self)

    def values(self) -> list[str]:
        return list(self._by_key.keys())

    def keys(self) -> list[Any]:
        return list(self._by_value.keys())

    def __repr__(self) -> str:
        return repr(self._by_key)

    def __str__(self) -> str:
        return str(self._by_key)


class Choice:
    """The choice object has an optional label and value. If the value is not
    given an autoincrementing id (starting from 1) will be used

    >>> choice = Choice('value', 'label')
    >>> choice
    <Choice[1]:label>
    >>> str(choice)
    'label'

    >>> choice = Choice()
    >>> choice
    <Choice[2]:None>
    >>> str(choice)
    'None'
    """

    # Class-level counter used to preserve definition order. Deliberately
    # not a `ClassVar`: instances shadow it with their own `order`.
    order: int = 0

    def __init__(
        self,
        value: Any = None,
        label: 'str | StrPromise | None' = None,
        **metadata: Any,
    ) -> None:
        Choice.order += 1
        self.value: Any = value
        self.label: str | StrPromise | None = label
        self.order = Choice.order
        self.metadata: dict[str, Any] = metadata

    def __getattr__(self, name: str) -> Any:
        # Only called when normal attribute lookup fails, so real
        # attributes (`value`, `label`, `order`, `metadata`) always win.
        try:
            return self.__dict__['metadata'][name]
        except KeyError:
            raise AttributeError(
                f'{type(self).__name__!r} object has no attribute {name!r}'
            ) from None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Choice):  # pragma: no branch
            return self.value == other.value
        else:
            return self.value == other

    def __repr__(self) -> str:
        return f'<{self.__class__.__name__}[{self.order:d}]:{self.label}>'

    def __str__(self) -> str:
        return self.__unicode__()

    def __unicode__(self) -> str:
        return str(self.label)

    def __hash__(self) -> int:
        return hash(self.value)

    def deconstruct(
        self,
    ) -> tuple[str, tuple[Any, 'str | StrPromise | None'], dict[str, Any]]:
        return (
            f'{self.__class__.__module__}.{self.__class__.__name__}',
            (self.value, self.label),
            {},
        )


class ChoicesMeta(type):
    """The choices metaclass is where all the magic happens, this
    automatically creates a ChoicesDict to get a sorted list of keys and
    values"""

    # Declared on the metaclass so `SomeChoices.choices` type-checks on
    # classes using this metaclass; the actual value is assigned in
    # `_assign_values` during class creation.
    choices: ChoicesDict

    def __new__(
        cls,
        name: str,
        bases: tuple[type, ...],
        attrs: dict[str, Any],
    ) -> 'ChoicesMeta':
        literal = cls._is_literal_choices(bases)
        choices, has_values = cls._collect_choices(attrs)
        cls._assign_values(attrs, choices, has_values, literal)

        # No `typing.cast` needed: typeshed types the 4-argument form of
        # `type.__new__` as returning `Self`, and mypy strict flags a cast
        # here as redundant.
        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def _is_literal_choices(bases: tuple[type, ...]) -> bool:
        # Chicken-Egg problem, can't check for something that doesn't exist
        # yet. That's why we check for the name of the class instead of a
        # `issubclass`
        return any(base.__name__ == 'LiteralChoices' for base in bases)

    @staticmethod
    def _collect_choices(
        attrs: dict[str, Any],
    ) -> tuple[list[tuple[str, Choice]], bool]:
        choices: list[tuple[str, Choice]] = []
        has_values = False
        raw_ignore = attrs.get('_ignore_', ())
        if isinstance(raw_ignore, str):
            raw_ignore = raw_ignore.replace(',', ' ').split()
        ignore: frozenset[str] = frozenset(raw_ignore)

        for key, value in attrs.items():
            # Skip private, protected and explicitly ignored values
            if key.startswith('_') or key in ignore:
                continue

            if isinstance(value, (str, int, float)):
                value = Choice(value, key.lower())

            if isinstance(value, Choice):
                if value.value is not None:
                    has_values = True

                if not value.label:
                    value.label = key.lower()

                choices.append((key, value))

        return choices, has_values

    @staticmethod
    def _assign_values(
        attrs: dict[str, Any],
        choices: list[tuple[str, Choice]],
        has_values: bool,
        literal: bool,
    ) -> None:
        attrs['choices'] = ChoicesDict()
        i = 0
        for key, value in sorted(choices, key=lambda c: c[1].order):
            if has_values:
                assert value.value is not None, (
                    'Cannot mix choices with and without values'
                )
            elif literal:
                value.value = value.label
            else:
                value.value = i
                i += 1

            attrs[key] = value.value
            attrs['choices'][key] = value

    def __iter__(cls) -> Iterator[tuple[Any, Choice]]:
        yield from cls.choices


class Choices(metaclass=ChoicesMeta):
    """The choices class is what you should inherit in your Django models

    >>> choices = Choices()
    >>> choices.choices[0]
    Traceback (most recent call last):
    ...
    KeyError: 'Key 0 does not exist'
    >>> choices.choices
    OrderedDict()
    >>> str(choices.choices)
    'OrderedDict()'
    >>> choices.choices.items()
    []
    >>> choices.choices.keys()
    []
    >>> choices.choices.values()
    []
    >>> list(choices)
    []

    >>> class ChoiceTest(Choices):
    ...     a = Choice()
    >>> choices = ChoiceTest()
    >>> choices.choices.items()
    [(0, <Choice[...]:a>)]
    >>> choices.a
    0
    >>> choices.choices['a']
    <Choice[...]:a>
    >>> choices.choices[0]
    <Choice[...]:a>
    >>> choices.choices.keys()
    [0]
    >>> choices.choices.values()
    ['a']
    >>> list(choices)
    [(0, <Choice[...]:a>)]
    >>> list(ChoiceTest)
    [(0, <Choice[...]:a>)]
    """

    choices = ChoicesDict()

    def __iter__(self) -> Iterator[tuple[Any, Choice]]:
        yield from self.choices


class LiteralChoices(Choices):
    """Special version of the Choices class that uses the label as the value

    >>> class Role(LiteralChoices):
    ...     admin = Choice()
    ...     user = Choice()
    ...     guest = Choice()

    >>> Role.choices.values()
    ['admin', 'user', 'guest']
    >>> Role.choices.keys()
    ['admin', 'user', 'guest']


    >>> class RoleWithImplicitChoice(LiteralChoices):
    ...     ADMIN = 'admin'
    ...     USER = 'user'
    ...     GUEST = 'guest'

    >>> Role.choices.values()
    ['admin', 'user', 'guest']
    >>> Role.choices.keys()
    ['admin', 'user', 'guest']
    >>> Role.admin
    'admin'
    """
