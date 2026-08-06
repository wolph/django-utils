# Dropdown filter demo

This page loads the same `dropdown_filter.js` and `dropdown_filter.css`
files the package installs — not a copy pasted into the docs — straight
from `_static/django_utils/admin/`. See
[dropdown / autocomplete filters](dropdown-filters) in {doc}`/admin`
for the full write-up, or read the source on GitHub:
[`dropdown_filter.js`](https://github.com/WoLpH/django-utils/blob/master/django_utils/static/django_utils/admin/dropdown_filter.js).

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

The markup below mirrors `dropdown_filter.html`'s CSP-safe rewrite: a
no-JS-safe link list, plus a `<select>` (rendered `hidden`, marked
`data-dropdown-filter`) that the script swaps in once JavaScript runs.
The template only renders that `<select>` when there are more than
three choices, so this demo lists four.

```{raw} html
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
<link rel="stylesheet" href="../_static/django_utils/admin/dropdown_filter.css">
<script src="../_static/django_utils/admin/dropdown_filter.js"></script>
```
