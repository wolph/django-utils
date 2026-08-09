# JSON widget demo

This page loads the same `json_widget.js` and `json_widget.css` files
the package installs, straight from `_static/django_utils/admin/`, not
a copy pasted into the docs. See [JSON widget](json-widget-section)
in {doc}`/admin` for the full write-up, or read the source on GitHub:
[`json_widget.js`](https://github.com/WoLpH/django-utils/blob/master/django_utils/static/django_utils/admin/json_widget.js).

The panel styling below is docs-only (in the admin it comes from the
admin's own stylesheets). Everything inside the panel is the shipped
markup contract and the shipped JavaScript.

**What to try**

- Type. Keys, strings, numbers and `true`/`false`/`null` are
  colorized live. The highlighting is a small tokenizer shipped in
  `json_widget.js` itself, painting a colored overlay over the still
  fully native `<textarea>`. No highlighting library, no
  dependencies.
- Delete the closing `}` (or otherwise break the JSON): an inline
  error appears below the textarea, using the browser's own
  `JSON.parse()` message. The colors keep working on broken JSON,
  because the highlighter lexes rather than parses.
- Fix it back to valid JSON and the error clears.
- With JavaScript disabled this degrades to a plain `<textarea>`.
  Django's own server-side validation still runs on submit.

The markup below mirrors exactly what `JSONWidget` renders in a real
`ModelAdmin` change form: a `<textarea>` carrying `data-json-widget`,
pre-formatted (indented, key-sorted) the way the widget's
`format_value()` renders a stored value.

```{raw} html
<div class="admin-demo-panel admin-demo-panel-wide">
<h3>Demo json</h3>
<textarea data-json-widget id="id_demo_json" name="demo_json" rows="10" cols="40">{
  "a": [
    1,
    2
  ],
  "b": 2,
  "enabled": true,
  "note": null
}</textarea>
</div>
<link rel="stylesheet" href="../_static/django_utils/admin/json_widget.css">
<script src="../_static/django_utils/admin/json_widget.js"></script>
```
