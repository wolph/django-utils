"""Sphinx configuration for django-utils2."""

import datetime
import importlib.metadata
import os
import sys

sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django

django.setup()

_metadata = importlib.metadata.metadata('django-utils2')

project = 'Django Utils 2'
author = 'Rick van Hattem (wolph)'
copyright = f'2012-{datetime.date.today().year}, {author}'
version = importlib.metadata.version('django-utils2')
release = version

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
]

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'django': (
        'https://docs.djangoproject.com/en/stable/',
        'https://docs.djangoproject.com/en/stable/_objects/',
    ),
}

templates_path = []
exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

html_theme = 'furo'
html_static_path = ['_static']
