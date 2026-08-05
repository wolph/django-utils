# Models & fields

Base model mixins for collision-free slugs and consistent
`__str__`/`__repr__` behaviour, metadata-carrying choices with a
real-`Enum` escape hatch, Fernet-encrypted fields for at-rest secrets
(with their non-goals stated loudly), and a native PostgreSQL enum
field with hand-written migration operations.

## Base models & slugs

`django_utils.base_models` gives Django models a more readable table
naming convention and three small, composable behaviours: automatic
`__str__`/`__unicode__`/`__repr__` derived from a `name` field
(`NameMixin`), automatic collision-free slugs derived from that same
`name` (`SlugMixin`), and automatic `created_at`/`updated_at`
timestamps (`CreatedAtModelBase`). `ModelBase` (via its metaclass)
also renames the default table from Django's `app_foobarobject` to
the more readable `app_foo_bar_object`, unless `Meta.db_table` is set
explicitly. Combine what you need through the ready-made bases:
`NameModelBase`, `SlugModelBase`, `NameCreatedAtModelBase`, and
`SlugCreatedAtModelBase`.

```python
from django_utils.base_models import SlugCreatedAtModelBase


class Article(SlugCreatedAtModelBase):
    pass


article = Article.objects.create(name='My First Post')
article.slug          # 'my-first-post'
str(article)           # 'My First Post'
repr(article)          # '<Article[1]: My First Post>'
```

:::{dropdown} Caveat: slugs are not unique at the database level by default
`SlugMixin` does **not** add a unique constraint on `slug` — its
nested `Meta.unique_together` is inert, since `SlugMixin` is not
itself a `Model` and a concrete subclass such as `SlugModelBase`
declares its own `Meta`, which does not inherit from this one. Models
that need the slug enforced unique at the database level should
declare `unique=True` on their own slug field.

`get_unique_slug()` probes via `_base_manager` — Django's documented
unfiltered manager — rather than `_default_manager`, so a model with a
filtered default manager (soft-delete style: `objects =
ActiveManager()`) still gets checked against every row in the table,
not just the ones its default manager happens to expose; otherwise two
rows hidden from each other by the filter could silently collide onto
the same slug.

The uniqueness check and the eventual insert are **not** atomic, so
two concurrent saves can still race each other onto the same slug.
Callers with high write concurrency on the same name should declare
`unique=True` on their own slug field and handle the resulting
`IntegrityError`.
:::

API reference: {py:class}`~django_utils.base_models.SlugMixin`,
{py:class}`~django_utils.base_models.SlugCreatedAtModelBase`, full
module at {doc}`django_utils`.

## Choices

Django 3.0+ ships native `models.TextChoices` / `models.IntegerChoices`
enums; `django_utils.choices` remains for the extra `Choice` metadata
and dict-like access it provides.

```python
from django_utils import choices


# For manually specifying the value (automatically detects `str`, `int` and `float`):
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = 'm'
        FEMALE = 'f'
        OTHER = 'o'

    gender = models.CharField(max_length=1, choices=Gender)


# To define the values as `male` implicitly:
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = choices.Choice()
        FEMALE = choices.Choice()
        OTHER = choices.Choice()

    gender = models.CharField(max_length=1, choices=Gender)


# Or explicitly define them
class Human(models.Model):
    class Gender(choices.Choices):
        MALE = choices.Choice('m', 'male')
        FEMALE = choices.Choice('f', 'female')
        OTHER = choices.Choice('o', 'other')

    gender = models.CharField(max_length=1, choices=Gender)
```

`Choice` also accepts arbitrary keyword metadata, reachable as
attributes on the resolved choice. Give a choice a `group` and
`grouped()` hands Django the nested structure it renders as
`<optgroup>`:

```python
class Status(choices.Choices):
    Active = choices.Choice('a', 'Active', color='green')
    Inactive = choices.Choice('i', 'Inactive', color='red')


Status.choices['a'].color  # 'green'


class Product(choices.Choices):
    Apple = choices.Choice('ap', 'Apple', group='Fruit')
    Carrot = choices.Choice('ca', 'Carrot', group='Vegetable')


field = models.CharField(max_length=2, choices=Product.choices.grouped())
```

`Choices.as_enum()` builds a real `enum.Enum` from the class without
touching the original, so model fields keep using the raw-value class
while application code gets `isinstance`/`match` support:

```python
StatusEnum = Status.as_enum()
StatusEnum('a') is StatusEnum.ACTIVE  # True
```

:::{dropdown} Caveat: enum picklability and caching
`as_enum()` is memoised per class: repeated calls return the *same*
enum class, so `Status.as_enum() is Status.as_enum()` and
`Status.as_enum().Active is Status.as_enum().Active` both hold, which
lets the enum be used as (or as part of) a dict/cache key. A subclass
builds and caches its own enum rather than inheriting its parent's.

The returned class is built dynamically with its `__module__` set to
`django_utils.choices` rather than the caller's module, so its members
are **not picklable** with the default pickle protocol — pickling an
enum member looks the class up by `__module__` + qualified name, which
won't resolve back to a class that was never assigned a name in that
module.
:::

API reference: {py:class}`~django_utils.choices.Choices`,
{py:class}`~django_utils.choices.Choice`.

(encrypted-model-fields)=
## Encrypted model fields

`EncryptedCharField`, `EncryptedTextField` and `EncryptedJSONField`
store a Fernet-encrypted token in a plain `TEXT` column — encryption
at rest for values you never need to query, sort or index by (an API
key, a bank account number, free-text notes). All crypto goes through
[`cryptography`](https://cryptography.io/)'s `Fernet`/`MultiFernet` —
nothing hand-rolled, no `hazmat` primitives touched directly. Requires
the `crypto` extra: `pip install "django-utils2[crypto]"`.

```python
from django.db import models
from django_utils.crypto_fields import (
    EncryptedCharField,
    EncryptedJSONField,
    EncryptedTextField,
)


class Customer(models.Model):
    tax_id = EncryptedCharField(max_length=20)
    notes = EncryptedTextField(blank=True)
    payment_details = EncryptedJSONField(null=True, blank=True)
```

Keys live in `settings.DJANGO_UTILS_FERNET_KEYS`, a list of
urlsafe-base64 32-byte keys (`Fernet.generate_key()`):

```python
DJANGO_UTILS_FERNET_KEYS = [
    'the-current-key...',
    'the-previous-key...',  # still needed to decrypt old rows
]
```

**Rotation story:** the FIRST key encrypts; EVERY key is tried on
decrypt. Rotate by prepending a new key and redeploying — existing
rows keep decrypting fine under the old key (now second in the list),
and get re-encrypted under the new (first) key the next time each row
is saved. There is no bulk re-encryption command here; touch
(`.save()`) the rows you want migrated on your own schedule, e.g. with
[`ChunkedCommand`](chunkedcommand). Once every row has
been resaved, drop the old key from the list — rows that were never
resaved under it become undecryptable (`ValidationError` on read) the
moment it's removed.

Importing `django_utils.crypto_fields` works without `cryptography`
installed; *instantiating* any of the three fields without it raises
`ImproperlyConfigured` naming that install command — and since fields
instantiate as part of executing a model's class body, a model that
*declares* one of them fails at app-import/`django.setup()` time, not
on first use: the whole app fails to boot, loudly and immediately, if
the extra is missing.

`EncryptedCharField`'s `max_length` validates the PLAINTEXT (a
`MaxLengthValidator`, same as plain `CharField`); it never sizes the
column, which always stores the necessarily-longer ciphertext instead.
`from_db_value` decrypts eagerly, as each row is fetched — a token
nothing in `DJANGO_UTILS_FERNET_KEYS` can decrypt raises
`ValidationError` out of the fetch itself (`.get()`,
`.refresh_from_db()`, iterating a queryset), not lazily on later
attribute access.

**Non-goals, loudly:**

- No queryable or searchable encryption. Fernet salts every
  encryption, so two rows with identical plaintext get different
  ciphertext — even `exact` can never match at the database level.
  Every lookup except `isnull` raises `NotImplementedError`; filter in
  Python after decrypting, or maintain a separate searchable hash
  column alongside the encrypted one. This includes this package's own
  admin features: a [`JSONFieldFilter`](operator-filters) or
  `search_fields` entry pointing at an encrypted field makes the
  changelist raise that same `NotImplementedError` at request time — a
  configuration error surfaced loudly, not a silent empty result.
- Ordering is not blocked (Django offers no field-level hook for it),
  but `order_by()` on an encrypted field sorts by ciphertext — a
  meaningless order. Don't.
- Encryption at rest only: anything that reads through the ORM sees
  plaintext — including this package's own [`ExportMixin`](admin-export)
  (an export action on an encrypted model streams decrypted values
  into the CSV/JSON download) and Django's `dumpdata` (fixtures land
  on disk in plaintext).
- No per-field keys. One keyring (`DJANGO_UTILS_FERNET_KEYS`) for
  every encrypted field in the project.
- No deterministic mode. If you need same-plaintext-same-ciphertext,
  this is the wrong tool — it also reintroduces exactly the equality
  side-channel Fernet's salting exists to prevent.

API reference: {py:class}`~django_utils.crypto_fields.EncryptedCharField`,
{py:class}`~django_utils.crypto_fields.EncryptedTextField`,
{py:class}`~django_utils.crypto_fields.EncryptedJSONField`.

## PostgreSQL ENUM field

`django_utils.pg_enum.EnumField` wires a `Choices` class straight to a
`CharField`: `choices` and `max_length` are derived from it, and on
PostgreSQL the column's real type is a native `CREATE TYPE ... AS ENUM`
type instead of `VARCHAR` — the database itself then rejects a row
that doesn't hold one of the declared values, on top of (not instead
of) Django's own choice validation.

::::{tab-set}

:::{tab-item} PostgreSQL
The column's real type is the native enum (`CREATE TYPE ... AS ENUM`).
An `INSERT`/`UPDATE` with a value outside the declared set is rejected
by the database itself, independent of and in addition to Django's own
`choices` validation.
:::

:::{tab-item} SQLite / everything else
`db_type()` falls back to plain `VARCHAR`, so a model using `EnumField`
stays portable — SQLite never sees a Postgres-specific type name, and
only Django's own `choices` validation applies.
:::

::::

```python
from django.db import models
from django_utils import choices, pg_enum


class OrderStatus(choices.Choices):
    Pending = choices.Choice('pending', 'Pending')
    Shipped = choices.Choice('shipped', 'Shipped')
    Delivered = choices.Choice('delivered', 'Delivered')


class Order(models.Model):
    status = pg_enum.EnumField(OrderStatus, default=OrderStatus.Pending)
```

`enum_type` defaults to the `Choices` class name in snake_case
(`OrderStatus` -> `'order_status'`); pass it explicitly to use a
different PostgreSQL type name.

### Hand-written migration operations

The field never issues DDL for the enum type itself — Django's
`makemigrations` autodetector has no concept of "create this
standalone database object first". Add explicit operations to a
migration BY HAND instead. All three operation classes are DB-only (no
model-state changes) and no-ops on every non-PostgreSQL vendor, so a
migration using them still applies cleanly against SQLite or MySQL —
just without the enum type's extra database-level integrity check.

::::{tab-set}

:::{tab-item} Initial type
`CreateEnumType` must run before the operation that adds a column
using it, so it belongs in the same migration, ahead of `AddField`:

```python
import myapp.models
from django.db import migrations
from django_utils import pg_enum


class Migration(migrations.Migration):
    dependencies = [...]

    operations = [
        pg_enum.CreateEnumType(
            'order_status', ['pending', 'shipped', 'delivered']
        ),
        migrations.AddField(
            model_name='order',
            name='status',
            field=pg_enum.EnumField(myapp.models.OrderStatus, default='pending'),
        ),
    ]
```

`CreateEnumType` reverses to `DROP TYPE`; `DropEnumType` is the
inverse (it takes the same `values` so *its* reversal has something to
recreate).
:::

:::{tab-item} Adding a value
`AddEnumValue` sets `atomic = False` on itself, but **that alone is
not enough**. Django's migration executor opens its schema editor —
and with it, the wrapping transaction — keyed on the **Migration's**
`atomic` attribute (default `True`), *before* any operation's own
`atomic` flag is ever consulted; an operation-level flag can only add
extra wrapping inside an already-open transaction, never escape one
that's already open. This is the same reason Django's own
`AddIndexConcurrently` requires `atomic = False` on the Migration
class, not just the operation. Skip it and
`AddEnumValue.database_forwards` raises `NotSupportedError` instead of
running somewhere it can't safely run:

```python
class Migration(migrations.Migration):
    dependencies = [...]
    atomic = False  # required -- see above; the operation's own
    # atomic = False cannot escape this Migration's transaction on its own.

    operations = [
        pg_enum.AddEnumValue('order_status', 'cancelled'),
    ]
```

`AddEnumValue` is also irreversible — PostgreSQL has no `DROP VALUE`
at all, on any version.
:::

:::{tab-item} Removing a value (escape hatch)
If you need to remove a value, recreate the type instead:

```python
class Migration(migrations.Migration):
    dependencies = [...]

    operations = [
        pg_enum.CreateEnumType(
            'order_status_v2', ['pending', 'shipped', 'delivered']
        ),
        # Plain `migrations.AlterField` won't work here: Django's own
        # autogenerated `ALTER COLUMN ... TYPE` has no `USING` clause, and
        # PostgreSQL refuses to cast one enum type to another without one
        # ("column ... cannot be cast automatically"). `SeparateDatabaseAndState`
        # splits the state change (the ORM now expects `enum_type='order_status_v2'`)
        # from the database change (an explicit two-step cast through
        # `text`, since PostgreSQL has no direct enum-to-enum cast either).
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    "ALTER TABLE myapp_order ALTER COLUMN status TYPE "
                    "order_status_v2 USING status::text::order_status_v2",
                    reverse_sql=(
                        "ALTER TABLE myapp_order ALTER COLUMN status TYPE "
                        "order_status USING status::text::order_status"
                    ),
                ),
            ],
            state_operations=[
                migrations.AlterField(
                    model_name='order',
                    name='status',
                    field=pg_enum.EnumField(
                        myapp.models.OrderStatus, enum_type='order_status_v2'
                    ),
                ),
            ],
        ),
        pg_enum.DropEnumType(
            'order_status', ['pending', 'shipped', 'delivered', 'cancelled']
        ),
    ]
```
:::

::::

API reference: {py:class}`~django_utils.pg_enum.EnumField`,
{py:class}`~django_utils.pg_enum.CreateEnumType`,
{py:class}`~django_utils.pg_enum.AddEnumValue`,
{py:class}`~django_utils.pg_enum.DropEnumType`.
