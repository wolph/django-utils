from django.test import override_settings
from django_utils.templatetags.debug import debug


class Secret:
    def __init__(self):
        self.public = 'shown'
        self._private = 'hidden'


@override_settings(DEBUG=False)
def test_debug_filter_is_silent_in_production():
    assert debug(Secret()).strip() == ''


@override_settings(DEBUG=True)
def test_debug_filter_hides_protected_attributes():
    output = debug(Secret())
    assert 'public' in output
    assert '_private' not in output


@override_settings(DEBUG=True)
def test_debug_filter_still_renders_values():
    assert '123' in debug(123)
