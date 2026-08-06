"""Throwaway Django settings for capturing admin screenshots.

Never touched outside `capture.py`: the six screenshots in this
directory's manifest need a real, running admin site to shoot, and
none of that setup belongs in `tests.settings` (the actual test
suite's settings). This module wires the same `tests.test_app` models
the test suite already exercises into a minimal admin-only project.
"""

import os

DEBUG = True

# `capture.py` sets this before this module is imported, in both the
# process that seeds the database and the `runserver` subprocess that
# serves it. A bare `:memory:` default would give the subprocess an
# empty database of its own -- sqlite's `:memory:` database is private
# to the connection that opened it, and the subprocess opens its own.
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.environ['DJANGO_UTILS_SCREENSHOT_DB'],
    }
}

ALLOWED_HOSTS: list[str] = ['127.0.0.1', 'localhost']

# Throwaway: generated fresh for this repo, never deployed, discarded
# with the tempdir database at the end of every `capture.py` run.
SECRET_KEY = 'django-utils2-screenshot-secret-key'

INSTALLED_APPS: list[str] = [
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.admin',
    'django_utils',
    'tests.test_app',
    'demo_project',
]

MIDDLEWARE: list[str] = [
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'demo_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# No STATIC_ROOT / STATICFILES_DIRS: `django.contrib.staticfiles`'s own
# `runserver` override auto-serves every installed app's `static/`
# directory (admin's, django_utils's) under `DEBUG = True` with no
# `collectstatic` step needed.
STATIC_URL = '/static/'

TIME_ZONE = 'UTC'
USE_TZ = True
LANGUAGE_CODE = 'en-us'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
