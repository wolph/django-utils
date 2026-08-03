"""Tests for django_utils.crypto_fields (Fernet-encrypted model fields)."""

import json

import pytest
from cryptography.fernet import Fernet
from django import forms
from django.core import (
    exceptions,
    validators as django_validators,
)
from django.db import connection
from django_utils import crypto_fields

from tests.test_app import models

pytestmark = pytest.mark.django_db

# Test-only key, not a credential: a second key distinct from the two in
# tests/settings.py, used only for the key-rotation scenario below.
_KEY_B = 'F_e2x9M8Jp4SAm0vkHT6bhXUMGp352DTc7Mfeshv__E='


def _raw_column(table: str, column: str, pk: int) -> str:
    with connection.cursor() as cursor:
        cursor.execute(
            f'SELECT {column} FROM {table} WHERE id = %s',  # noqa: S608
            [pk],
        )
        row = cursor.fetchone()
    assert row is not None
    return row[0]


# -- Round-trip via the DB ---------------------------------------------


def test_char_field_round_trips_via_db():
    secret = models.Secret.objects.create(
        char_value='hello', text_value='x', json_value=None
    )
    secret.refresh_from_db()
    assert secret.char_value == 'hello'


def test_text_field_round_trips_non_ascii_via_db():
    text = 'héllo wörld 日本語'
    secret = models.Secret.objects.create(
        char_value='x', text_value=text, json_value=None
    )
    secret.refresh_from_db()
    assert secret.text_value == text


def test_json_field_round_trips_nested_structure_via_db():
    payload = {'a': [1, 2, {'b': 'c'}], 'd': None, 'e': True}
    secret = models.Secret.objects.create(
        char_value='x', text_value='y', json_value=payload
    )
    secret.refresh_from_db()
    assert secret.json_value == payload


def test_none_round_trips_as_null():
    secret = models.Secret.objects.create(
        char_value='x', text_value='y', json_value=None
    )
    secret.refresh_from_db()
    assert secret.json_value is None
    raw = _raw_column('test_app_secret', 'json_value', secret.pk)
    assert raw is None


# -- Stored column is a Fernet token, not plaintext ---------------------


@pytest.mark.parametrize(
    ('field_name', 'column'),
    [('char_value', 'char_value'), ('text_value', 'text_value')],
)
def test_stored_column_is_a_fernet_token(field_name, column):
    plaintext = 'super-secret-value'
    kwargs = {'char_value': 'x', 'text_value': 'y', 'json_value': None}
    kwargs[field_name] = plaintext
    secret = models.Secret.objects.create(**kwargs)

    raw = _raw_column('test_app_secret', column, secret.pk)

    assert raw.startswith('gAAAA')
    assert plaintext not in raw


def test_stored_json_column_is_a_fernet_token_and_hides_plaintext():
    secret = models.Secret.objects.create(
        char_value='x', text_value='y', json_value={'password': 'hunter2'}
    )

    raw = _raw_column('test_app_secret', 'json_value', secret.pk)

    assert raw.startswith('gAAAA')
    assert 'hunter2' not in raw
    assert 'password' not in raw


# -- Key rotation --------------------------------------------------------


def test_key_rotation_read_then_reencrypt_then_drop_old_key(settings):
    key_new = 'Q7LBlcU2P375f2K8lYWJkEzEVxTuiR_vf9u1rGbBnPU='
    settings.DJANGO_UTILS_FERNET_KEYS = [_KEY_B]

    # Both rows are encrypted under the (only, soon-to-be-dropped) key A.
    rotated = models.Secret.objects.create(
        char_value='rotate-me', text_value='y', json_value=None
    )
    stale = models.Secret.objects.create(
        char_value='never-resaved', text_value='y', json_value=None
    )
    original_token = _raw_column('test_app_secret', 'char_value', rotated.pk)

    # Prepend a new key; the old key can still decrypt existing rows.
    settings.DJANGO_UTILS_FERNET_KEYS = [key_new, _KEY_B]
    rotated.refresh_from_db()
    assert rotated.char_value == 'rotate-me'

    # Saving re-encrypts under the new first key: the raw column changes.
    rotated.save()
    reencrypted_token = _raw_column(
        'test_app_secret', 'char_value', rotated.pk
    )
    assert reencrypted_token != original_token

    # With only the new key configured, the STALE row (never re-saved,
    # still encrypted under the now-dropped key A) can no longer decrypt.
    # Decryption runs as a `from_db_value` converter while the row is
    # fetched, so the raise happens on refresh_from_db() itself, not on
    # a later attribute access.
    settings.DJANGO_UTILS_FERNET_KEYS = [key_new]
    with pytest.raises(exceptions.ValidationError):
        stale.refresh_from_db()


# -- Missing / malformed settings ----------------------------------------


def test_missing_fernet_keys_setting_raises_improperly_configured_on_save(
    settings,
):
    del settings.DJANGO_UTILS_FERNET_KEYS
    secret = models.Secret(char_value='x', text_value='y', json_value=None)
    with pytest.raises(exceptions.ImproperlyConfigured):
        secret.save()


def test_malformed_fernet_key_raises_improperly_configured(settings):
    settings.DJANGO_UTILS_FERNET_KEYS = ['not-a-valid-fernet-key']
    secret = models.Secret(char_value='x', text_value='y', json_value=None)
    with pytest.raises(exceptions.ImproperlyConfigured):
        secret.save()


# -- Lookups: everything but isnull is blocked ---------------------------


@pytest.mark.parametrize('lookup', ['exact', 'icontains', 'gt'])
def test_non_isnull_lookups_raise_not_implemented(lookup):
    with pytest.raises(NotImplementedError):
        models.Secret.objects.filter(**{f'char_value__{lookup}': 'x'})


def test_isnull_lookup_works():
    models.Secret.objects.create(
        char_value='x', text_value='y', json_value=None
    )
    models.Secret.objects.create(
        char_value='x', text_value='y', json_value={'a': 1}
    )
    assert models.Secret.objects.filter(json_value__isnull=True).count() == 1
    assert models.Secret.objects.filter(json_value__isnull=False).count() == 1


# -- EncryptedCharField max_length validates plaintext -------------------


def test_max_length_validates_plaintext_not_the_stored_token():
    secret = models.Secret(
        char_value='x' * 101, text_value='y', json_value=None
    )
    with pytest.raises(exceptions.ValidationError) as excinfo:
        secret.full_clean()
    assert 'char_value' in excinfo.value.message_dict


def test_char_field_without_max_length_skips_the_validator():
    field = crypto_fields.EncryptedCharField()
    assert field.max_length is None
    assert not any(
        isinstance(v, django_validators.MaxLengthValidator)
        for v in field.validators
    )


def test_max_length_allows_plaintext_at_the_limit_despite_longer_token():
    secret = models.Secret(
        char_value='x' * 100, text_value='y', json_value=None
    )
    secret.full_clean()  # must not raise
    secret.save()
    raw = _raw_column('test_app_secret', 'char_value', secret.pk)
    # The Fernet token for 100 chars of plaintext is comfortably longer
    # than the 100-char plaintext max_length it was validated against.
    assert len(raw) > 100


# -- Missing cryptography dependency --------------------------------------


def test_field_instantiation_without_cryptography_raises(monkeypatch):
    monkeypatch.setattr(crypto_fields, '_fernet_available', False)
    with pytest.raises(exceptions.ImproperlyConfigured) as excinfo:
        crypto_fields.EncryptedTextField()
    assert "pip install 'django-utils2[crypto]'" in str(excinfo.value)


# -- deconstruct() leaks no keys -------------------------------------------


def test_deconstruct_contains_no_key_material():
    field = models.Secret._meta.get_field('char_value')
    _name, _path, args, kwargs = field.deconstruct()

    serialized = repr(args) + repr(kwargs)
    for key in (
        '9LSCQxpLl8Xfl9ogBCyDLhFXirKhVtNLpmuEShBJPc4=',
        'Q7LBlcU2P375f2K8lYWJkEzEVxTuiR_vf9u1rGbBnPU=',
    ):
        assert key not in serialized


# -- Sanity: Fernet key literals used above are real, valid keys ---------


def test_key_b_constant_is_a_valid_fernet_key():
    Fernet(_KEY_B)  # must not raise


def test_json_value_serializes_through_json_dumps_loads():
    # Regression guard for the serializer hooks themselves, independent
    # of the DB round-trip above.
    field = crypto_fields.EncryptedJSONField()
    value = {'x': 1}
    assert field._deserialize(json.dumps(value)) == value


# -- formfield() overrides: ModelForm/admin must not corrupt values ------


def test_json_value_round_trips_through_a_modelform():
    """Regression: a bare Field.formfield() defaults to forms.CharField,
    which never parses submitted text as JSON -- get_prep_value() then
    re-encrypts the raw *string* `'{"a": 1}'` instead of the dict, and
    reload silently returns a str where a dict is expected. No error at
    any layer -- this is a silent data-corruption bug, not a crash.
    """
    secret = models.Secret.objects.create(
        char_value='x', text_value='y', json_value=None
    )
    form_class = forms.modelform_factory(models.Secret, fields=['json_value'])
    form = form_class(data={'json_value': '{"a": 1}'}, instance=secret)

    assert form.is_valid(), form.errors
    saved = form.save()

    saved.refresh_from_db()
    assert saved.json_value == {'a': 1}
    assert isinstance(saved.json_value, dict)


def test_json_value_form_rejects_invalid_json_without_saving():
    secret = models.Secret.objects.create(
        char_value='x', text_value='y', json_value={'untouched': True}
    )
    form_class = forms.modelform_factory(models.Secret, fields=['json_value'])
    form = form_class(data={'json_value': '{not json'}, instance=secret)

    assert not form.is_valid()
    assert 'json_value' in form.errors

    secret.refresh_from_db()
    assert secret.json_value == {'untouched': True}


def test_text_value_formfield_uses_a_textarea_widget():
    field = models.Secret._meta.get_field('text_value')
    formfield = field.formfield()
    assert isinstance(formfield.widget, forms.Textarea)


def test_char_value_formfield_carries_max_length():
    field = models.Secret._meta.get_field('char_value')
    formfield = field.formfield()
    assert formfield.max_length == 100
    attrs = formfield.widget_attrs(formfield.widget)
    assert attrs['maxlength'] == '100'


@pytest.mark.django_db
def test_queryset_update_encrypts():
    """`update()` routes through `get_prep_value` without `Model.save()`
    -- the raw column must still hold a Fernet token, never plaintext."""
    secret = models.Secret.objects.create(
        char_value='old', text_value='t', json_value=None
    )
    models.Secret.objects.update(char_value='updated-plain')

    secret.refresh_from_db()
    assert secret.char_value == 'updated-plain'
    raw = _raw_column('test_app_secret', 'char_value', secret.pk)
    assert raw.startswith('gAAAA')
    assert 'updated-plain' not in raw


@pytest.mark.django_db
def test_bulk_create_encrypts():
    """`bulk_create` also bypasses `Model.save()`; same contract."""
    models.Secret.objects.bulk_create(
        [
            models.Secret(
                char_value='bulk-plain', text_value='t', json_value=None
            )
        ]
    )

    secret = models.Secret.objects.get()
    assert secret.char_value == 'bulk-plain'
    raw = _raw_column('test_app_secret', 'char_value', secret.pk)
    assert raw.startswith('gAAAA')
    assert 'bulk-plain' not in raw
