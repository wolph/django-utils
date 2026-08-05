# Quickstart

Install django-utils2, add it to `INSTALLED_APPS`, and get three
concrete wins in the time it takes to read this page — no extra
configuration beyond the app entry below unless a specific feature
(encrypted fields, PostgreSQL enums) calls for its own setting.

## Install

```bash
pip install django-utils2
```

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
