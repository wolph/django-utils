# Dropdown filter demo

This page loads the same `dropdown_filter.js` and `dropdown_filter.css`
files the package installs — not a copy pasted into the docs — straight
from `_static/django_utils/admin/`. See
[dropdown / autocomplete filters](dropdown-filters) in {doc}`/admin`
for the full write-up, or read the source on GitHub:
[`dropdown_filter.js`](https://github.com/WoLpH/django-utils/blob/master/django_utils/static/django_utils/admin/dropdown_filter.js).

The panel styling below is docs-only (in the admin it comes from the
admin's own stylesheets); everything inside the panel is the shipped
markup contract and the shipped JavaScript.

## Plain dropdown

The base `DropdownFilter` is a native `<select>` — no autocomplete; for
that, see the [select2 variant](#select2-variant) below.

**What to try**

- With JavaScript disabled, the link list below *is* the whole filter
  — each link is a working, no-JS filter option.
- With JavaScript enabled (the normal case), the script hides the
  links and unhides the `<select>` in their place — the admin's usual
  dropdown UX, restored without an inline `onchange` handler.
- Pick an option in the dropdown: the shipped script navigates to
  `window.location.pathname + <option value>`. On a real changelist
  that value is a query string like `?field=value`; here every
  option's value is a harmless `?demo=...`, so choosing one just
  reloads this page with that query string appended — nothing breaks.

The markup mirrors `dropdown_filter.html`'s CSP-safe rewrite: a
no-JS-safe link list, plus a `<select>` (rendered `hidden`, marked
`data-dropdown-filter`) that the script swaps in once JavaScript runs.
The template only renders that `<select>` when there are more than
three choices, so this demo lists four.

```{raw} html
<div class="admin-demo-panel">
<h3>By category</h3>
<ul class="admin-filter-demo django-utils-dropdown-filter">
    <li class="selected"><a href="?demo=">All</a></li>
    <li><a href="?demo=fruit">Fruit</a></li>
    <li><a href="?demo=vegetable">Vegetable</a></li>
    <li><a href="?demo=other">Other</a></li>
    <li>
    <select class="form-control" hidden data-dropdown-filter id="id_demo_dropdown">
    <option selected="selected" value="?demo=">All</option>
    <option value="?demo=fruit">Fruit</option>
    <option value="?demo=vegetable">Vegetable</option>
    <option value="?demo=other">Other</option>
    </select>
    </li>
</ul>
</div>
<link rel="stylesheet" href="../_static/django_utils/admin/dropdown_filter.css">
<script src="../_static/django_utils/admin/dropdown_filter.js"></script>
```

(select2-variant)=

## Select2 variant

The `*Select2` filters (`AllValuesFieldListFilterSelect2`,
`JSONFieldFilterSelect2`, …) layer typing autocomplete onto the exact
same markup: `select2_filter.html` extends `dropdown_filter.html`, adds
`data-select2-filter` to the `<select>`, and loads `select2_filter.js`
— which activates select2 only when the admin's vendored jQuery +
select2 are on the page, and silently falls back to the plain dropdown
when they aren't. On a real changelist those vendored assets arrive via
`Select2Mixin.Media`; this page loads the same files from the installed
Django the docs are built against.

**What to try**

- Click the dropdown: select2 opens with a search box — type to filter
  the options live (try `av` or `beef`).
- Pick an option: the *same* shipped `change` navigation as the plain
  dropdown fires — select2 replaces the widget, not the behavior.
- Block or delete the vendored select2 script in devtools and reload:
  the filter degrades to the plain dropdown above, never to a broken
  widget.

```{raw} html
<div class="admin-demo-panel">
<h3>By filling</h3>
<ul class="admin-filter-demo django-utils-dropdown-filter">
    <li class="selected"><a href="?demo=">All</a></li>
    <li><a href="?demo=avocado">Avocado</a></li>
    <li><a href="?demo=bacon">Bacon</a></li>
    <li><a href="?demo=cheddar">Cheddar</a></li>
    <li><a href="?demo=corned-beef">Corned Beef</a></li>
    <li><a href="?demo=egg">Egg</a></li>
    <li><a href="?demo=ham">Ham</a></li>
    <li><a href="?demo=pastrami">Pastrami</a></li>
    <li><a href="?demo=turkey">Turkey</a></li>
    <li>
    <select class="form-control" hidden data-dropdown-filter data-select2-filter id="filling">
    <option selected="selected" value="?demo=">All</option>
    <option value="?demo=avocado">Avocado</option>
    <option value="?demo=bacon">Bacon</option>
    <option value="?demo=cheddar">Cheddar</option>
    <option value="?demo=corned-beef">Corned Beef</option>
    <option value="?demo=egg">Egg</option>
    <option value="?demo=ham">Ham</option>
    <option value="?demo=pastrami">Pastrami</option>
    <option value="?demo=turkey">Turkey</option>
    </select>
    </li>
</ul>
</div>
<link rel="stylesheet" href="../_static/admin/css/vendor/select2/select2.css">
<script src="../_static/admin/js/vendor/jquery/jquery.js"></script>
<script src="../_static/admin/js/vendor/select2/select2.full.js"></script>
<script src="../_static/admin/js/jquery.init.js"></script>
<script src="../_static/django_utils/admin/select2_filter.js"></script>
```
