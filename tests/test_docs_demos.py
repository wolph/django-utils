"""The docs demo pages embed hand-written copies of the widgets' markup
and load the real shipped JS. If the data-attribute contract between
them drifts, the demos silently die -- these tests pin the contract
without needing a docs build."""

from pathlib import Path

DOCS = Path(__file__).parent.parent / 'docs'
STATIC = Path(__file__).parent.parent / 'django_utils' / 'static'


def _read(path):
    return path.read_text(encoding='utf-8')


def test_json_widget_demo_matches_shipped_contract():
    demo = _read(DOCS / 'demos' / 'json-widget.md')
    shipped = _read(STATIC / 'django_utils' / 'admin' / 'json_widget.js')
    assert 'data-json-widget' in demo
    assert 'data-json-widget' in shipped
    assert 'django_utils/admin/json_widget.js' in demo


def test_json_widget_highlight_classes_are_styled():
    """Every token class the highlighter emits must have a color rule
    (light and dark) in the shipped stylesheet, and the overlay's own
    class must exist in both files -- a renamed class on either side
    silently kills the highlighting."""
    shipped_js = _read(STATIC / 'django_utils' / 'admin' / 'json_widget.js')
    shipped_css = _read(STATIC / 'django_utils' / 'admin' / 'json_widget.css')
    for token_class in (
        'django-utils-json-key',
        'django-utils-json-string',
        'django-utils-json-number',
        'django-utils-json-literal',
        'django-utils-json-highlight',
    ):
        assert token_class in shipped_js, token_class
        assert token_class in shipped_css, token_class
    # Dark-theme parity: the admin's dark and auto themes both restyle
    # every token class.
    for scope in ("html[data-theme='dark']", "html[data-theme='auto']"):
        for token_class in ('key', 'string', 'number', 'literal'):
            assert (
                f'{scope} .django-utils-json-{token_class}' in shipped_css
            ), (scope, token_class)


def test_dropdown_demo_matches_shipped_contract():
    demo = _read(DOCS / 'demos' / 'dropdown-filter.md')
    shipped = _read(STATIC / 'django_utils' / 'admin' / 'dropdown_filter.js')
    assert 'data-dropdown-filter' in demo
    assert 'data-dropdown-filter' in shipped
    assert 'django_utils/admin/dropdown_filter.js' in demo


def test_select2_demo_matches_shipped_contract():
    demo = _read(DOCS / 'demos' / 'dropdown-filter.md')
    shipped = _read(STATIC / 'django_utils' / 'admin' / 'select2_filter.js')
    assert 'data-select2-filter' in demo
    assert 'data-select2-filter' in shipped
    assert 'django_utils/admin/select2_filter.js' in demo
    # select2 announces selections through jQuery's event system only;
    # without this native-`change` bridge, dropdown_filter.js's
    # navigation listener never fires and picking an option silently
    # does nothing (the 4.1.0 bug).
    assert 'select2:select' in shipped
    assert "dispatchEvent(new Event('change'" in shipped
    # The vendored assets the demo loads must be the ones the shipped
    # script requires (django.jQuery + select2, wired by jquery.init.js).
    for vendored in (
        'admin/js/vendor/jquery/jquery.js',
        'admin/js/vendor/select2/select2.full.js',
        'admin/js/jquery.init.js',
        'admin/css/vendor/select2/select2.css',
    ):
        assert vendored in demo, vendored


def test_demo_pages_are_csp_clean():
    import re

    handler_re = re.compile(r'\son[a-z]+\s*=', re.IGNORECASE)
    for name in ('json-widget.md', 'dropdown-filter.md'):
        source = _read(DOCS / 'demos' / name)
        assert not handler_re.search(source), name
        assert 'style=' not in source, name
