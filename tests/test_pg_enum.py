"""Tests for django_utils.pg_enum.

Sqlite-side tests run everywhere and cover the field's derivation logic
and the migration operations' no-op behaviour on a non-PostgreSQL
backend. Postgres-marked tests (``@pytest.mark.postgres``) exercise the
real DDL against a live PostgreSQL connection and only run under
``DJANGO_UTILS_TEST_POSTGRES=1`` (see ``tests/conftest.py``).
"""

import typing

import pytest
from django.core import exceptions as dj_exceptions
from django.db import (
    Error as DjangoDbError,
    connection,
    transaction,
)
from django.db.migrations.exceptions import IrreversibleError
from django.test.utils import CaptureQueriesContext
from django_utils import choices, pg_enum

from tests.test_app import models

# transaction=True file-wide: SQLite's schema editor disables FK-constraint
# checking on __enter__, which SQLite cannot do mid-transaction -- and a
# plain `django_db` test already has one open (its own savepoint-wrapped
# transaction). Nearly every test here opens a real `schema_editor()`
# (directly or via the `order_table` fixture), so this needs to be file-wide
# rather than a handful of per-test overrides.
pytestmark = pytest.mark.django_db(transaction=True)

# Some tests specifically exercise the non-PostgreSQL code path (db_type's
# varchar fallback, the operations' vendor-guarded no-op). Phase D's test
# infra can also run this whole *sqlite-named* test module against a real
# PostgreSQL connection (`DJANGO_UTILS_TEST_POSTGRES=1` swaps every
# connection, not just `@pytest.mark.postgres`-marked tests), so those
# specific tests are meaningless there and must be skipped -- the
# `@pytest.mark.postgres` tests below cover the same ground on Postgres.
requires_non_postgres = pytest.mark.skipif(
    connection.vendor == 'postgresql',
    reason='exercises the non-Postgres code path; see the postgres-marked '
    'equivalents below',
)

_ORDER_VALUES = list(models.OrderStatus.choices.keys())
_ORDER_ENUM_TYPE = typing.cast(
    'pg_enum.EnumField', models.Order._meta.get_field('status')
).enum_type


@pytest.fixture
def order_table() -> typing.Iterator[None]:
    """Create, then drop, ``Order``'s table (and its enum type) for a test.

    ``Order`` is ``managed = False`` (see ``tests/test_app/models.py``)
    precisely so plain syncdb never tries to create its PostgreSQL enum
    column before the enum type exists. This fixture creates the type
    then the table -- the same order a hand-written migration would use
    (``CreateEnumType`` before ``CreateModel``/``AddField``) -- and tears
    both down afterwards.
    """
    create_type = pg_enum.CreateEnumType(_ORDER_ENUM_TYPE, _ORDER_VALUES)
    with connection.schema_editor() as schema_editor:
        create_type.database_forwards('test_app', schema_editor, None, None)
        schema_editor.create_model(models.Order)
    yield
    with connection.schema_editor() as schema_editor:
        schema_editor.delete_model(models.Order)
        create_type.database_backwards('test_app', schema_editor, None, None)


# --- EnumField: derivation -------------------------------------------------


def test_choices_derived_from_choices_class():
    field = pg_enum.EnumField(models.OrderStatus)
    assert field.choices == [
        ('pending', 'Pending'),
        ('shipped', 'Shipped'),
        ('delivered', 'Delivered'),
    ]


def test_max_length_auto_derived():
    field = pg_enum.EnumField(models.OrderStatus)
    assert field.max_length == len('delivered')


def test_max_length_explicit_override_respected():
    field = pg_enum.EnumField(models.OrderStatus, max_length=99)
    assert field.max_length == 99


def test_enum_type_default_snake_case():
    field = pg_enum.EnumField(models.OrderStatus)
    assert field.enum_type == 'order_status'


def test_enum_type_explicit_override_respected():
    field = pg_enum.EnumField(models.OrderStatus, enum_type='custom_enum')
    assert field.enum_type == 'custom_enum'


def test_empty_choices_class_raises():
    class Empty(choices.Choices):
        pass

    with pytest.raises(ValueError, match='defines no choices'):
        pg_enum.EnumField(Empty)


def test_choices_kwarg_conflicts_with_derivation():
    """``choices`` is always derived -- passing it too is a caller bug."""
    with pytest.raises(TypeError, match='choices'):
        pg_enum.EnumField(models.OrderStatus, choices=[('x', 'X')])


# --- EnumField: db_type -----------------------------------------------------


@requires_non_postgres
def test_db_type_sqlite_is_varchar():
    field = pg_enum.EnumField(models.OrderStatus)
    assert field.db_type(connection) == f'varchar({field.max_length})'


# --- EnumField: sqlite round trip -------------------------------------------


def test_full_model_round_trip_sqlite(order_table):
    order = models.Order.objects.create(status=models.OrderStatus.Shipped)
    order.refresh_from_db()
    assert order.status == models.OrderStatus.Shipped


def test_full_clean_rejects_non_choice_value(order_table):
    order = models.Order(status='not-a-real-status')
    with pytest.raises(dj_exceptions.ValidationError):
        order.full_clean()


# --- EnumField: deconstruct --------------------------------------------------


def test_deconstruct_round_trip():
    field = pg_enum.EnumField(models.OrderStatus)
    _name, _path, args, kwargs = field.deconstruct()
    new_field = field.__class__(*args, **kwargs)
    assert new_field.choices_class is field.choices_class
    assert new_field.choices == field.choices
    assert new_field.max_length == field.max_length
    assert new_field.enum_type == field.enum_type


def test_deconstruct_omits_derived_redundancy():
    field = pg_enum.EnumField(models.OrderStatus)
    _name, _path, args, kwargs = field.deconstruct()
    assert 'choices' not in kwargs
    assert 'max_length' not in kwargs
    assert 'enum_type' not in kwargs
    assert args == [models.OrderStatus]


def test_deconstruct_keeps_explicit_max_length_override():
    field = pg_enum.EnumField(models.OrderStatus, max_length=99)
    _name, _path, _args, kwargs = field.deconstruct()
    assert kwargs['max_length'] == 99


def test_deconstruct_keeps_explicit_enum_type_override():
    field = pg_enum.EnumField(models.OrderStatus, enum_type='custom_enum')
    _name, _path, _args, kwargs = field.deconstruct()
    assert kwargs['enum_type'] == 'custom_enum'


# --- Operations: no-ops on sqlite -------------------------------------------


@requires_non_postgres
def test_create_enum_type_noop_and_describe_on_sqlite():
    op = pg_enum.CreateEnumType('some_enum', ['a', 'b'])
    op.state_forwards('test_app', None)
    with connection.schema_editor() as schema_editor:
        with CaptureQueriesContext(connection) as ctx:
            op.database_forwards('test_app', schema_editor, None, None)
        assert ctx.captured_queries == []
    with connection.schema_editor() as schema_editor:
        with CaptureQueriesContext(connection) as ctx:
            op.database_backwards('test_app', schema_editor, None, None)
        assert ctx.captured_queries == []
    assert (
        op.describe() == "Create PostgreSQL ENUM type 'some_enum' ('a', 'b')"
    )


@requires_non_postgres
def test_drop_enum_type_noop_and_describe_on_sqlite():
    op = pg_enum.DropEnumType('some_enum', ['a', 'b'])
    op.state_forwards('test_app', None)
    with connection.schema_editor() as schema_editor:
        with CaptureQueriesContext(connection) as ctx:
            op.database_forwards('test_app', schema_editor, None, None)
        assert ctx.captured_queries == []
    with connection.schema_editor() as schema_editor:
        with CaptureQueriesContext(connection) as ctx:
            op.database_backwards('test_app', schema_editor, None, None)
        assert ctx.captured_queries == []
    assert op.describe() == "Drop PostgreSQL ENUM type 'some_enum'"


@requires_non_postgres
def test_add_enum_value_noop_forwards_on_sqlite():
    op = pg_enum.AddEnumValue('some_enum', 'c')
    op.state_forwards('test_app', None)
    with connection.schema_editor() as schema_editor:
        with CaptureQueriesContext(connection) as ctx:
            op.database_forwards('test_app', schema_editor, None, None)
        assert ctx.captured_queries == []
    assert op.describe() == "Add value 'c' to PostgreSQL ENUM type 'some_enum'"


def test_add_enum_value_atomic_is_false():
    assert pg_enum.AddEnumValue('some_enum', 'c').atomic is False


def test_add_enum_value_reversal_raises_irreversible():
    op = pg_enum.AddEnumValue('some_enum', 'c')
    with connection.schema_editor() as schema_editor:
        with pytest.raises(IrreversibleError):
            op.database_backwards('test_app', schema_editor, None, None)


# --- Postgres-marked ---------------------------------------------------------


@pytest.mark.postgres
def test_enum_field_db_type_on_postgres():
    field = pg_enum.EnumField(models.OrderStatus, enum_type='pg_enum_dbtype')
    assert field.db_type(connection) == connection.ops.quote_name(
        'pg_enum_dbtype'
    )


@pytest.mark.postgres
def test_create_enum_type_then_raw_sql_insert():
    type_name = 'pg_enum_test_color'
    table_name = 'pg_enum_test_color_table'
    op = pg_enum.CreateEnumType(type_name, ['red', 'green', 'blue'])
    with connection.schema_editor() as schema_editor:
        op.database_forwards('test_app', schema_editor, None, None)
        schema_editor.execute(
            f'CREATE TABLE {schema_editor.quote_name(table_name)} '
            f'(id serial primary key, '
            f'color {schema_editor.quote_name(type_name)})'
        )
    with connection.cursor() as cursor:
        cursor.execute(
            f'INSERT INTO {connection.ops.quote_name(table_name)} '
            f"(color) VALUES ('red')"
        )
        cursor.execute(
            f'SELECT COUNT(*) FROM {connection.ops.quote_name(table_name)}'
        )
        assert cursor.fetchone()[0] == 1

    # An undeclared value is rejected by PostgreSQL itself. Wrapped in its
    # own savepoint so the failed statement doesn't poison the rest of the
    # test's (auto-rolled-back) outer transaction.
    with pytest.raises(DjangoDbError), transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO {connection.ops.quote_name(table_name)} '
                f"(color) VALUES ('purple')"
            )


@pytest.mark.postgres
def test_drop_enum_type_removes_from_catalog():
    type_name = 'pg_enum_test_dropme'
    create_op = pg_enum.CreateEnumType(type_name, ['x', 'y'])
    with connection.schema_editor() as schema_editor:
        create_op.database_forwards('test_app', schema_editor, None, None)
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_type WHERE typname = %s', [type_name])
        assert cursor.fetchone() is not None

    drop_op = pg_enum.DropEnumType(type_name, ['x', 'y'])
    with connection.schema_editor() as schema_editor:
        drop_op.database_forwards('test_app', schema_editor, None, None)
    with connection.cursor() as cursor:
        cursor.execute('SELECT 1 FROM pg_type WHERE typname = %s', [type_name])
        assert cursor.fetchone() is None


@pytest.mark.postgres
def test_end_to_end_schema_editor_create_model(order_table):
    order = models.Order.objects.create(status=models.OrderStatus.Pending)
    order.refresh_from_db()
    assert order.status == models.OrderStatus.Pending

    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT udt_name FROM information_schema.columns '
            'WHERE table_name = %s AND column_name = %s',
            [models.Order._meta.db_table, 'status'],
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == _ORDER_ENUM_TYPE


@pytest.mark.postgres
def test_add_enum_value_then_insert_new_value():
    """``ALTER TYPE ... ADD VALUE`` cannot run inside an open transaction.

    The module-wide ``transaction=True`` (real commits, no enclosing
    transaction) is necessary but not sufficient here -- combined with
    ``connection.schema_editor(atomic=False)`` below, the ``ALTER TYPE``
    runs genuinely outside any transaction. Since nothing auto-rolls-back in
    this mode, cleanup is explicit and manual (``finally``).
    """
    type_name = 'pg_enum_test_priority'
    table_name = 'pg_enum_test_priority_table'
    create_op = pg_enum.CreateEnumType(type_name, ['low', 'high'])
    try:
        with connection.schema_editor() as schema_editor:
            create_op.database_forwards('test_app', schema_editor, None, None)
            schema_editor.execute(
                f'CREATE TABLE {schema_editor.quote_name(table_name)} '
                f'(id serial primary key, '
                f'priority {schema_editor.quote_name(type_name)})'
            )

        add_value_op = pg_enum.AddEnumValue(type_name, 'critical')
        with connection.schema_editor(atomic=False) as schema_editor:
            add_value_op.database_forwards(
                'test_app', schema_editor, None, None
            )

        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO {connection.ops.quote_name(table_name)} '
                f'(priority) VALUES (%s)',
                ['critical'],
            )
            cursor.execute(
                f'SELECT COUNT(*) FROM '
                f'{connection.ops.quote_name(table_name)} '
                f"WHERE priority = 'critical'"
            )
            assert cursor.fetchone()[0] == 1
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                f'DROP TABLE IF EXISTS {connection.ops.quote_name(table_name)}'
            )
        with connection.schema_editor() as schema_editor:
            pg_enum.DropEnumType(
                type_name, ['low', 'high', 'critical']
            ).database_forwards('test_app', schema_editor, None, None)
