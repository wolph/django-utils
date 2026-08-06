# Quickstart

Install django-utils2, add it to `INSTALLED_APPS`, and get three
concrete wins in the time it takes to read this page — no extra
configuration beyond the app entry below unless a specific feature
(encrypted fields, PostgreSQL enums) calls for its own setting.

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
Successfully installed django-utils2-4.1.0
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

## Three 2-minute wins

Three small, independent changes, each usable on its own without
adopting the rest of the library.

### JSON sub-path filter on an admin

If a model has a `JSONField`, filter the changelist on a value nested
inside it — no custom `SimpleListFilter` to write:

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

**What you get:** a changelist sidebar filter on `data['filling']` —
no JOIN, no denormalized column, no hand-written `SimpleListFilter` —
see [Select / dropdown / autocomplete filters](dropdown-filters).

### `count_columns` on an admin

Add sortable related-object counts to `list_display` without the N+1
a naive `list_display` method causes, or the JOIN fan-out
`annotate(Count(...))` causes the moment a second relation joins it:

```python
from django.contrib import admin
from django_utils.admin.mixins import CountColumnMixin

from myapp.models import Sandwich


class SandwichAdmin(CountColumnMixin, admin.ModelAdmin):
    list_display = ('id',)
    count_columns = ('review', 'topping')


admin.site.register(Sandwich, SandwichAdmin)
```

**What you get:** sortable `review_count` and `topping_count` columns,
each counted in its own subquery so a second relation never multiplies
the first — see [Count columns](count-columns).

### `query_budget` around a hot view

Wrap a view to catch N+1 regressions where they actually happen — in
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

**What you get:** a logged warning past 20 queries and a raised
`QueryBudgetExceeded` past 100, counted through Django's own
`connection.execute_wrapper()` so it costs nothing with `DEBUG` off —
see [Query budgets](query-budgets).
