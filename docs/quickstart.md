# Quickstart

Install django-utils2, add it to `INSTALLED_APPS`, and pick from the
three small features below. Each works on its own and needs no
configuration beyond the app entry. Features that do need a setting,
such as the encrypted fields, name it on their own page.

## Install

```bash
pip install django-utils2
```

Optional extras, installed with `pip install "django-utils2[<extra>]"`:

| Extra | Installs | Needed for |
| --- | --- | --- |
| `crypto` | `cryptography>=42.0` | [Encrypted model fields](encrypted-model-fields): `EncryptedCharField`, `EncryptedTextField`, `EncryptedJSONField` |

### Verify the install

<pre data-terminal>
$ pip install django-utils2
Collecting django-utils2
Installing collected packages: django-utils2
Successfully installed django-utils2-4.1.1
$ python -m django check
System check identified no issues (0 silenced).
</pre>

## Add to `INSTALLED_APPS`

```python
INSTALLED_APPS = [
    ...,
    'django_utils',
]
```

## Three features to start with

Three small, independent changes, each usable on its own without
adopting the rest of the library.

### JSON sub-path filter on an admin

If a model has a `JSONField`, filter the changelist on a value nested
inside it without writing a custom `SimpleListFilter`:

```python
from django.contrib import admin
from django_utils.admin.filters import JSONFieldFilterDropdown

from myapp.models import Sandwich


class SandwichAdmin(admin.ModelAdmin):
    list_filter = (
        JSONFieldFilterDropdown.create('data__filling'),
    )


admin.site.register(Sandwich, SandwichAdmin)
```

This adds a sidebar filter on `data['filling']` to the changelist. No
JOIN, no denormalized column, no hand-written filter class. The whole
filter family is covered in
[Select / dropdown / autocomplete filters](dropdown-filters).

### `count_columns` on an admin

Add sortable related-object counts to `list_display`. A count method
on the admin costs one query per row, and `annotate(Count(...))`
starts multiplying counts the moment a second relation joins the
query. `count_columns` avoids both:

```python
from django.contrib import admin
from django_utils.admin.mixins import CountColumnMixin

from myapp.models import Sandwich


class SandwichAdmin(CountColumnMixin, admin.ModelAdmin):
    list_display = ('id',)
    count_columns = ('review', 'topping')


admin.site.register(Sandwich, SandwichAdmin)
```

The `review_count` and `topping_count` columns sort like any other
column, and each relation is counted in its own subquery, so a second
relation never inflates the first. Details in
[Count columns](count-columns).

### `query_budget` around a hot view

Wrap a view to catch N+1 regressions where they actually happen, in
production, not only inside a test's `assertNumQueries`:

```python
from django.shortcuts import render

from django_utils.query_debug import query_budget
from myapp.models import Sandwich


@query_budget(warn_at=20, raise_at=100)
def sandwich_list(request):
    sandwiches = Sandwich.objects.all()
    return render(request, 'sandwiches/list.html', {'sandwiches': sandwiches})
```

Past 20 queries the view logs a warning, past 100 it raises
`QueryBudgetExceeded`. The counting runs through Django's own
`connection.execute_wrapper()`, so it costs nothing with `DEBUG` off.
Details in [Query budgets](query-budgets).
