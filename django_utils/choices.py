'''
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

        gender = models.CharField(max_length=1, choices=Gender.choices)

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

        enum = models.IntegerField(
            choices=Enum.choices, default=Enum.Foo)

To reference these properties:

.. code-block:: python

    SomeModel.create(enum=SomeModel.Enum.Spam)

'''
import six
import collections


class ChoicesDict(object):

    '''The choices dict is an object that stores a sorted representation of
    the values by key and database value'''

    def __init__(self):
        self._by_value = collections.OrderedDict()
        self._by_key = collections.OrderedDict()

        # Reset the choice creation counter since this will only be accessed
        # after processing the choices
        Choice.order = 0

    def __getitem__(self, key):
        if key in self._by_value:
            return self._by_value[key]
        elif key in self._by_key:
            return self._by_key[key]
        else:
            raise KeyError('Key %r does not exist' % key)

    def __setitem__(self, key, value):
        self._by_key[key] = value
        self._by_value[value.value] = value

    def __iter__(self):
        for value, choice in six.iteritems(self._by_value):
            yield value, choice.label

    def items(self):
        return list(self)

    def __repr__(self):
        return repr(self._by_key)

    def __str__(self):
        return six.text_type(self._by_key)


class Choice(object):

    '''The choice object has an optional label and value. If the value is not
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

    '''
    order = 0

    def __init__(self, value=None, label=None):
        Choice.order += 1
        self.value = value
        self.label = label
        self.order = Choice.order

    def __repr__(self):
        repr_ = (six.text_type('<%s[%d]:%s>') % (
            self.__class__.__name__,
            self.order,
            self.label,
        ))
        if six.PY2:
            repr_ = repr_.encode('utf-8', 'replace')
        return repr_

    def __str__(self):
        value = self.__unicode__()
        if six.PY2:
            value = value.encode('utf-8', 'replace')
        return value

    def __unicode__(self):
        label = self.label
        if six.PY2:
            if isinstance(label, str):
                return label.decode('utf-8', 'replace')
            else:
                return six.text_type(label)
        elif six.PY3:
            return six.text_type(label)


class ChoicesMeta(type):

    '''The choices metaclass is where all the magic happens, this
    automatically creates a ChoicesDict to get a sorted list of keys and
    values'''

    def __new__(cls, name, bases, attrs):
        choices = list()
        has_values = False
        for key, value in six.iteritems(attrs):
            if isinstance(value, Choice):
                if value.value:
                    has_values = True

                if not value.label:
                    value.label = key

                choices.append((key, value))

        attrs['choices'] = ChoicesDict()
        i = 0
        for key, value in sorted(choices, key=lambda c: c[1].order):
            if has_values:
                assert value.value, ('Cannot mix choices with and without '
                                     'values')
            else:
                value.value = i
                i += 1

            attrs[key] = value.value
            attrs['choices'][key] = value

        return super(ChoicesMeta, cls).__new__(cls, name, bases, attrs)


class Choices(six.with_metaclass(ChoicesMeta)):

    '''The choices class is what you should inherit in your Django models

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

    >>> class ChoiceTest(Choices):
    ...     a = Choice()
    >>> choices = ChoiceTest()
    >>> choices.choices.items()
    [(0, <Choice[3]:a>)]
    >>> choices.a
    0
    >>> choices.choices['a']
    <Choice[3]:a>
    >>> choices.choices[0]
    <Choice[3]:a>
    '''
    pass
