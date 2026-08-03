"""Fernet-encrypted model fields, behind the ``crypto`` extra.

``EncryptedCharField``, ``EncryptedTextField`` and ``EncryptedJSONField``
store a base64 Fernet token in a plain ``TEXT`` column
(``get_internal_type()`` returns ``'TextField'`` for all three, so the
column is always sized for ciphertext, never plaintext).  Encryption uses
:mod:`cryptography`'s ``Fernet``/``MultiFernet`` exclusively -- nothing
hand-rolled, no ``hazmat`` primitives touched directly.

Keys come from ``settings.DJANGO_UTILS_FERNET_KEYS``, a list of
urlsafe-base64 32-byte keys (``Fernet.generate_key()``). The FIRST key
encrypts; EVERY key is tried on decrypt (``MultiFernet``). Rotate by
prepending a new key and redeploying: old rows keep decrypting under the
old key until they are next saved, at which point they are re-encrypted
under the new (first) key. There is no bulk re-encryption command here --
touch (``.save()``) the rows you want migrated, or run your own
``queryset_iterator``-based pass over the table.

Non-goals, loudly: this is encryption at rest for values you never need
to query, sort or index by. There is no queryable/searchable mode, no
per-field keys, and no deterministic (same-plaintext-same-ciphertext)
mode -- Fernet salts every encryption, so even two rows with identical
plaintext get different ciphertext, and equality can never match at the
database level. Every lookup except ``isnull`` therefore raises
``NotImplementedError``; filter in Python after decrypting, or maintain a
separate searchable hash column alongside the encrypted one if you need
to find rows by value.

Requires the ``crypto`` extra (``pip install 'django-utils2[crypto]'``):
importing this module works without ``cryptography`` installed, but
instantiating any of the three fields raises ``ImproperlyConfigured``
with that install hint. Fields instantiate as part of executing a
model's class body, so a model that *declares* one of them fails at
app-import/``django.setup()`` time without the extra -- the whole app
fails to boot, loudly and immediately, not a deferred per-use error.
"""

import json
import typing
from typing import TYPE_CHECKING

from django import forms
from django.conf import settings
from django.core import exceptions, validators
from django.db import models

try:
    from cryptography.fernet import Fernet, InvalidToken, MultiFernet
except ImportError:  # pragma: no cover -- exercised via the sentinel below,
    # not by actually uninstalling the dependency in the test environment.
    _fernet_available = False
else:
    _fernet_available = True

if TYPE_CHECKING:
    from cryptography.fernet import Fernet, InvalidToken, MultiFernet
    from django.db.backends.base.base import BaseDatabaseWrapper
    from django.db.models import Expression
    from django.db.models.lookups import Lookup, Transform

_INSTALL_HINT = (
    "django_utils.crypto_fields requires the 'cryptography' package. "
    "Install it with: pip install 'django-utils2[crypto]'"
)

_NOT_QUERYABLE = (
    'encrypted fields are not queryable; filter in Python or store a '
    'searchable hash alongside'
)


def _get_keys() -> list[str]:
    keys = getattr(settings, 'DJANGO_UTILS_FERNET_KEYS', None)
    if not keys:
        raise exceptions.ImproperlyConfigured(
            'settings.DJANGO_UTILS_FERNET_KEYS must be set to a '
            'non-empty list of Fernet keys before using '
            'django_utils.crypto_fields (the first key encrypts; '
            'every key is tried on decrypt).'
        )
    return list(keys)


def _load_fernet() -> 'MultiFernet':
    try:
        return MultiFernet([Fernet(key) for key in _get_keys()])
    except ValueError as exc:
        raise exceptions.ImproperlyConfigured(
            'settings.DJANGO_UTILS_FERNET_KEYS contains a malformed '
            'Fernet key (expected 32 url-safe base64-encoded bytes '
            'each).'
        ) from exc


if TYPE_CHECKING:
    # ``Field`` is only ``Generic[_ST, _GT]`` in django-stubs, not at
    # runtime -- ``Field[Any, Any]`` as an actual base class raises
    # ``TypeError: type 'Field' is not subscriptable``.
    _FieldBase = models.Field[typing.Any, typing.Any]
else:
    _FieldBase = models.Field


class _EncryptedField(_FieldBase):
    """Shared Fernet encrypt/decrypt machinery.

    Private: not part of the public API. ``EncryptedCharField``,
    ``EncryptedTextField`` and ``EncryptedJSONField`` below are thin
    subclasses that each supply ``_serialize``/``_deserialize``.
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        if not _fernet_available:
            raise exceptions.ImproperlyConfigured(_INSTALL_HINT)
        super().__init__(*args, **kwargs)

    def get_internal_type(self) -> str:
        return 'TextField'

    def _serialize(self, value: typing.Any) -> str:
        raise NotImplementedError

    def _deserialize(self, value: str) -> typing.Any:
        raise NotImplementedError

    def get_prep_value(self, value: typing.Any) -> str | None:
        value = super().get_prep_value(value)
        if value is None:
            return None
        plaintext = self._serialize(value).encode()
        token = _load_fernet().encrypt(plaintext)
        return token.decode()

    def from_db_value(
        self,
        value: str | None,
        expression: 'Expression',
        connection: 'BaseDatabaseWrapper',
    ) -> typing.Any:
        """Decrypt eagerly, as each row is fetched.

        This runs as a query-result converter, not lazily on attribute
        access -- so a token nothing in ``DJANGO_UTILS_FERNET_KEYS`` can
        decrypt raises ``ValidationError`` out of the fetch itself (e.g.
        ``.get()``, ``.refresh_from_db()``, iterating a queryset), before
        any Python code sees a value for the field at all.
        """
        if value is None:
            return None
        try:
            plaintext = _load_fernet().decrypt(value.encode())
        except InvalidToken as exc:
            raise exceptions.ValidationError(
                'cannot decrypt; value encrypted with an unknown key?'
            ) from exc
        return self._deserialize(plaintext.decode())

    def get_lookup(self, lookup_name: str) -> 'type[Lookup] | None':
        if lookup_name == 'isnull':
            return super().get_lookup(lookup_name)
        raise NotImplementedError(_NOT_QUERYABLE)

    def get_transform(self, lookup_name: str) -> 'type[Transform] | None':
        raise NotImplementedError(_NOT_QUERYABLE)


class EncryptedCharField(_EncryptedField):
    """Fernet-encrypted ``str``, stored as a TEXT column.

    ``max_length`` validates the PLAINTEXT via a ``MaxLengthValidator``
    (mirroring plain ``CharField``'s own behaviour); it never sizes the
    column, which stores the necessarily-longer ciphertext instead.
    """

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__(*args, **kwargs)
        if self.max_length is not None:
            self.validators.append(
                validators.MaxLengthValidator(self.max_length)
            )

    def _serialize(self, value: typing.Any) -> str:
        return str(value)

    def _deserialize(self, value: str) -> str:
        return value

    def formfield(  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        self, **kwargs: typing.Any
    ) -> forms.Field | None:
        # Same idiom as CharField.formfield(): client-side maxlength and
        # server-side validation both see the same limit. Narrower
        # **kwargs-only signature than Field.formfield's (form_class,
        # choices_form_class, **kwargs) -- same shape django-stubs itself
        # uses (and silences) for every built-in Field subclass.
        kwargs.setdefault('max_length', self.max_length)
        return super().formfield(**kwargs)


class EncryptedTextField(_EncryptedField):
    """Fernet-encrypted, unbounded ``str``, stored as a TEXT column."""

    def _serialize(self, value: typing.Any) -> str:
        return str(value)

    def _deserialize(self, value: str) -> str:
        return value

    def formfield(  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        self, **kwargs: typing.Any
    ) -> forms.Field | None:
        # Same idiom as TextField.formfield(): a Textarea widget instead
        # of the single-line input a bare Field.formfield() would default
        # to.
        kwargs.setdefault('widget', forms.Textarea)
        return super().formfield(**kwargs)


class EncryptedJSONField(_EncryptedField):
    """Fernet-encrypted JSON-serializable value, stored as TEXT."""

    def _serialize(self, value: typing.Any) -> str:
        return json.dumps(value)

    def formfield(  # type: ignore[override]  # pyright: ignore[reportIncompatibleMethodOverride]
        self, **kwargs: typing.Any
    ) -> forms.Field | None:
        # Without this, bare Field.formfield() defaults to forms.CharField,
        # which never parses submitted text as JSON -- _serialize() would
        # then re-encode the raw string, silently corrupting the value on
        # every save through a ModelForm/admin. forms.JSONField parses (and
        # validates) it first.
        kwargs.setdefault('form_class', forms.JSONField)
        return super().formfield(**kwargs)

    def _deserialize(self, value: str) -> typing.Any:
        return json.loads(value)
