import html as htmllib
import json

from django import forms
from django_utils.admin import widgets


class JSONForm(forms.Form):
    data = forms.JSONField(widget=widgets.JSONWidget)


def _textarea_body(rendered):
    inner = rendered.split('>', 1)[1].rsplit('<', 1)[0]
    return htmllib.unescape(inner).strip()


def test_valid_json_is_pretty_printed_and_key_sorted():
    form = JSONForm(initial={'data': {'b': 2, 'a': [1, 2]}})
    body = _textarea_body(str(form['data']))
    assert body == json.dumps({'a': [1, 2], 'b': 2}, indent=2, sort_keys=True)
    assert '\n' in body


def test_malformed_input_still_round_trips_unchanged():
    """Django preserves InvalidJSONInput; the widget must not interfere."""
    form = JSONForm({'data': '{"a": 1,,,}'})
    assert not form.is_valid()
    assert _textarea_body(str(form['data'])) == '{"a": 1,,,}'


def test_widget_declares_its_media():
    media = str(widgets.JSONWidget().media)
    assert 'django_utils/admin/json_widget.js' in media
    assert 'django_utils/admin/json_widget.css' in media


def test_rendered_markup_is_csp_safe():
    rendered = str(JSONForm(initial={'data': {'a': 1}})['data'])
    assert '<script' not in rendered.lower()
    assert 'onclick=' not in rendered.lower()
    assert 'oninput=' not in rendered.lower()
    assert 'style=' not in rendered.lower()


def test_attrs_are_merged_with_the_data_widget_default():
    widget = widgets.JSONWidget(attrs={'rows': 5})
    assert widget.attrs['rows'] == 5
    assert widget.attrs['data-json-widget'] is True


def test_format_value_passes_through_non_string_values():
    assert widgets.JSONWidget().format_value(None) is None
