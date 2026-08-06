# JSON widget demo

This page loads the same `json_widget.js` and `json_widget.css` files
the package installs — not a copy pasted into the docs — straight from
`_static/django_utils/admin/`. See [JSON widget](json-widget-section)
in {doc}`/admin` for the full write-up, or read the source on GitHub:
[`json_widget.js`](https://github.com/WoLpH/django-utils/blob/master/django_utils/static/django_utils/admin/json_widget.js).

**What to try**

- Delete the closing `}` (or otherwise break the JSON) — an inline
  error appears below the textarea, using the browser's own
  `JSON.parse()` message.
- Fix it back to valid JSON — the error clears.
- With JavaScript disabled this degrades to a plain `<textarea>`;
  Django's own server-side validation still runs on submit.

The markup below mirrors exactly what `JSONWidget` renders in a real
`ModelAdmin` change form: a `<textarea>` carrying `data-json-widget`,
pre-formatted (indented, key-sorted) the way the widget's
`format_value()` renders a stored value.

```{raw} html
<textarea data-json-widget id="id_demo_json" name="demo_json" rows="10" cols="40">{
  "a": [
    1,
    2
  ],
  "b": 2
}</textarea>
<link rel="stylesheet" href="../_static/django_utils/admin/json_widget.css">
<script src="../_static/django_utils/admin/json_widget.js"></script>
```
