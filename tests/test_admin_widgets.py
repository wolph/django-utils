import html as htmllib
import json
import re

from django import forms
from django.contrib import admin
from django.db import models as db_models
from django_utils.admin import widgets

from tests.test_app import models as app_models

# Matches any `on*=` event-handler attribute (`onclick=`, `oninput=`,
# `onerror=`, ...), not just the couple of names a hand-picked list of
# `assert 'onclick=' not in rendered` checks would happen to cover.
HANDLER_ATTR_RE = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)


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
    assert not HANDLER_ATTR_RE.search(rendered)
    assert 'style=' not in rendered.lower()


def test_attrs_are_merged_with_the_data_widget_default():
    widget = widgets.JSONWidget(attrs={'rows': 5})
    assert widget.attrs['rows'] == 5
    assert widget.attrs['data-json-widget'] is True


def test_format_value_passes_through_non_string_values():
    assert widgets.JSONWidget().format_value(None) is None


def test_mixin_applies_the_widget_to_jsonfields():
    class SandwichAdmin(widgets.JSONWidgetMixin, admin.ModelAdmin):
        pass

    model_admin = SandwichAdmin(app_models.Sandwich, admin.AdminSite())
    form_field = model_admin.formfield_for_dbfield(
        app_models.Sandwich._meta.get_field('data'), request=None
    )
    assert isinstance(form_field.widget, widgets.JSONWidget)


def test_importing_the_package_does_not_change_the_global_default():
    """Installing for the filters alone must not alter anyone's forms."""
    default = db_models.JSONField().formfield().widget
    assert not isinstance(default, widgets.JSONWidget)
