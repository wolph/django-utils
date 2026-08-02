import pytest
from django.db import models
from django_utils import choices

try:
    from django.utils.translation import gettext_lazy as _
except ImportError:
    from django.utils.translation import ugettext_lazy as _


@pytest.fixture(autouse=True)
def _reset_choice_order():
    """`Choice.order` is a module-global counter; keep tests hermetic."""
    choices.Choice.order = 0
    yield
    choices.Choice.order = 0


class TranslatedHuman(models.Model):
    class Gender(choices.Choices):
        Male = choices.Choice('m', _('Male'))
        Female = choices.Choice('f', _('Female'))
        Other = choices.Choice('o', _('Other'))

    gender = models.CharField(max_length=1, choices=Gender.choices)

    class Meta:
        app_label = 'tests'


class Human(models.Model):
    class Gender(choices.Choices):
        Male = choices.Choice('m')
        Female = choices.Choice('f')
        Other = choices.Choice('o')

    gender = models.CharField(max_length=1, choices=Gender.choices)

    class Meta:
        app_label = 'tests'


class SomeModel(models.Model):
    class Enum(choices.Choices):
        Foo = choices.Choice()
        Bar = choices.Choice()
        Spam = choices.Choice()
        Eggs = choices.Choice()

    enum = models.IntegerField(choices=Enum.choices, default=Enum.Foo)

    class Meta:
        app_label = 'tests'


def test_named_choices():
    Human(gender=Human.Gender.Male)


def test_unnamed_choices():
    SomeModel(enum=SomeModel.Enum.Spam)


def test_choices():
    repr(Human.Gender)
    str(Human.Gender)


def test_choice():
    repr(Human.Gender.Male)
    str(Human.Gender.Male)


def test_choice_equals():
    choice_a = choices.Choice(value=123, label='123')
    choice_b = choices.Choice(value=123)
    choice_c = choices.Choice(value=456, label='123')

    assert choice_a != 'test'
    assert choice_a == 123
    assert choice_a != 456
    assert choice_a == choice_a
    assert choice_a == choice_b
    assert choice_a != choice_c
    assert hash(choice_a) != hash(choice_c)
    assert hash(choice_a) == hash(choice_b)


def test_choice_deconstruct():
    choices.Choice().deconstruct()
    choices.Choice(value=123).deconstruct()
    choices.Choice(value=123, label='123').deconstruct()


def test_choices_meta_is_not_polluted():
    class Pollution(choices.LiteralChoices):
        UNIQUE_POLLUTION_PROBE = 'probe'

    assert Pollution.UNIQUE_POLLUTION_PROBE == 'probe'
    assert not hasattr(choices.ChoicesMeta, 'UNIQUE_POLLUTION_PROBE')


def test_ignore_excludes_constants_from_choices():
    class Gender(choices.Choices):
        _ignore_ = ('MAX_LENGTH',)
        MAX_LENGTH = 1
        Male = choices.Choice('m')

    labels = [choice.label for _value, choice in Gender.choices.items()]
    assert 'max_length' not in labels
    assert 'male' in labels
    assert Gender.MAX_LENGTH == 1


def test_ignore_accepts_a_whitespace_or_comma_separated_string():
    """`_ignore_` accepts the string form stdlib `enum` also accepts."""

    class Gender(choices.Choices):
        _ignore_ = 'MAX_LENGTH, OTHER_CONSTANT'
        MAX_LENGTH = 1
        OTHER_CONSTANT = 2
        Male = choices.Choice('m')

    labels = [choice.label for _value, choice in Gender.choices.items()]
    assert 'max_length' not in labels
    assert 'other_constant' not in labels
    assert 'male' in labels
    assert Gender.MAX_LENGTH == 1
    assert Gender.OTHER_CONSTANT == 2


def test_constants_are_still_collected_without_ignore():
    """Without `_ignore_` the historical behaviour is unchanged."""

    class Gender(choices.Choices):
        MAX_LENGTH = 1
        Male = choices.Choice('m')

    labels = [choice.label for _value, choice in Gender.choices.items()]
    assert 'max_length' in labels


def test_choice_without_metadata_is_unchanged():
    """Existing two-argument usage must behave exactly as before."""

    class Gender(choices.Choices):
        Male = choices.Choice('m', 'Male')
        Female = choices.Choice('f')

    assert Gender.Male == 'm'
    assert Gender.Female == 'f'
    assert Gender.choices['m'].label == 'Male'
    assert Gender.choices['f'].label == 'female'
    assert Gender.choices['m'].metadata == {}


def test_choice_carries_arbitrary_metadata():
    class Status(choices.Choices):
        Active = choices.Choice('a', 'Active', color='green', weight=10)
        Closed = choices.Choice('c', 'Closed', color='red', weight=20)

    assert Status.choices['a'].color == 'green'
    assert Status.choices['a'].weight == 10
    assert Status.choices['c'].metadata == {'color': 'red', 'weight': 20}


def test_choice_metadata_does_not_shadow_real_attributes():
    """`value`, `label` and `order` are attributes, not metadata."""
    choice = choices.Choice('v', 'l', color='blue')
    assert choice.value == 'v'
    assert choice.label == 'l'
    assert choice.metadata == {'color': 'blue'}


def test_choice_unknown_attribute_raises_attribute_error():
    choice = choices.Choice('v', 'l')
    with pytest.raises(AttributeError):
        _ = choice.nonexistent


def test_as_enum_produces_real_enum_members():
    import enum

    class Gender(choices.Choices):
        Male = choices.Choice('m', 'Male')
        Female = choices.Choice('f', 'Female')

    # PascalCase: this is bound to a class (a dynamically built `Enum`
    # subclass), not a regular variable.
    GenderEnum = Gender.as_enum()  # noqa: N806

    # `GenderEnum` is typed as `type[enum.Enum]` (the functional API's
    # typeshed stub can't express the member names it creates at
    # runtime), so ty sees a base `Enum` with no `Male`/`Female`
    # attribute below. The same opacity is why a dynamically-built enum
    # can't be statically checked for `match` exhaustiveness either --
    # narrowly suppressed here rather than typed around.
    assert issubclass(GenderEnum, enum.Enum)
    assert GenderEnum.Male.value == 'm'  # ty: ignore[unresolved-attribute]
    assert GenderEnum('f') is GenderEnum.Female  # ty: ignore[unresolved-attribute]
    assert GenderEnum['Male'] is GenderEnum.Male  # ty: ignore[unresolved-attribute]
    assert isinstance(GenderEnum.Male, GenderEnum)  # ty: ignore[unresolved-attribute]
    assert [member.name for member in GenderEnum] == ['Male', 'Female']


def test_as_enum_leaves_the_original_class_untouched():
    class Gender(choices.Choices):
        Male = choices.Choice('m')

    Gender.as_enum()

    assert Gender.Male == 'm'
    # No explicit label was given, so the pre-existing (unchanged) default
    # applies: the lowercased attribute name, not 'Male'.
    assert Gender.choices['m'].label == 'male'


def test_as_enum_is_memoised():
    """Repeated calls must return the *same* enum class, not a fresh one
    each time -- otherwise ``is`` comparisons, ``match`` on members, and
    using a member as a dict/cache key all silently break, and pickling
    a member raises ``PicklingError`` (a fresh class per call is never
    importable by qualified name).
    """

    class Gender(choices.Choices):
        Male = choices.Choice('m', 'Male')
        Female = choices.Choice('f', 'Female')

    first = Gender.as_enum()
    second = Gender.as_enum()

    assert first is second
    assert first.Male is second.Male  # ty: ignore[unresolved-attribute]


def test_as_enum_subclass_gets_its_own_distinct_enum():
    """A subclass must not inherit its parent's cached enum: the cache
    lookup has to check ``cls.__dict__`` directly rather than
    ``getattr``/``setattr``, which would walk the MRO and hand the
    subclass the parent's class object instead of building its own.
    """

    class Gender(choices.Choices):
        Male = choices.Choice('m', 'Male')

    class ExtendedGender(Gender):
        Female = choices.Choice('f', 'Female')

    parent_enum = Gender.as_enum()
    child_enum = ExtendedGender.as_enum()

    assert parent_enum is not child_enum
    assert child_enum is ExtendedGender.as_enum()


def test_grouped_emits_djangos_optgroup_structure():
    class Product(choices.Choices):
        Apple = choices.Choice('ap', 'Apple', group='Fruit')
        Pear = choices.Choice('pe', 'Pear', group='Fruit')
        Carrot = choices.Choice('ca', 'Carrot', group='Vegetable')

    assert Product.choices.grouped() == [
        ('Fruit', [('ap', 'Apple'), ('pe', 'Pear')]),
        ('Vegetable', [('ca', 'Carrot')]),
    ]


def test_grouped_puts_ungrouped_choices_first_under_an_empty_group():
    class Mixed(choices.Choices):
        Plain = choices.Choice('p', 'Plain')
        Grouped = choices.Choice('g', 'Grouped', group='Some Group')

    assert Mixed.choices.grouped() == [
        ('', [('p', 'Plain')]),
        ('Some Group', [('g', 'Grouped')]),
    ]


def test_grouped_preserves_declaration_order_not_alphabetical():
    """`Fruit`/`Vegetable` in the tests above sort identically in
    declaration order and alphabetical order, so they don't tell the two
    apart. Declare the group that sorts later alphabetically first, to
    prove it's declaration order -- not a sort -- that determines the
    emitted order.
    """

    class Product(choices.Choices):
        Courgette = choices.Choice('c', 'Courgette', group='Zucchini')
        Braeburn = choices.Choice('b', 'Braeburn', group='Apple')

    assert Product.choices.grouped() == [
        ('Zucchini', [('c', 'Courgette')]),
        ('Apple', [('b', 'Braeburn')]),
    ]


def test_grouped_keeps_gettext_lazy_labels_lazy():
    """``grouped()`` must not eagerly resolve a ``gettext_lazy`` label
    (regression test for the label freezing at import time): the
    module docstring's own example calls ``grouped()`` at model-field
    definition time, so a multilingual site would otherwise get labels
    permanently stuck in whatever language happened to be active then.
    """
    from django.utils.functional import Promise

    class Status(choices.Choices):
        Active = choices.Choice('a', _('Active'), group='Group')

    [(group_key, [(value, label)])] = Status.choices.grouped()
    assert group_key == 'Group'
    assert value == 'a'
    assert isinstance(label, Promise)
    assert str(label) == 'Active'
