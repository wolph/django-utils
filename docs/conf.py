"""Sphinx configuration for django-utils2."""

import datetime
import importlib.metadata
import os
import pathlib
import shutil
import sys

sys.path.insert(0, os.path.abspath('..'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tests.settings')

import django
import django.contrib.admin

django.setup()

project = 'Django Utils 2'
author = 'Rick van Hattem (wolph)'
copyright = f'2012-{datetime.date.today().year}, {author}'
version = importlib.metadata.version('django-utils2')
release = version

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.intersphinx',
    'sphinx.ext.viewcode',
    'myst_parser',
    'sphinx_design',
    'sphinx_copybutton',
]

myst_enable_extensions = ['colon_fence']

# Straight ASCII quotes and hyphens only, in source and in the rendered
# site: the smartquotes transform would otherwise turn them back into
# typographic quotes and dashes at build time.
smartquotes = False

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'django': (
        'https://docs.djangoproject.com/en/stable/',
        'https://docs.djangoproject.com/en/stable/_objects/',
    ),
}

templates_path = []
# `superpowers/` is SDD planning scaffolding (specs, plans, progress
# ledgers) — git-ignored (see ~/.gitignore), not part of the published
# site. It only became reachable once `.md` joined `source_suffix`
# below; exclude it the same way `_build` already is.
# `screenshots/` is the admin-screenshot capture pipeline (`capture.py`,
# the throwaway `demo_project/`, its own `README.md`) -- source code and
# its own docs, not a page of this site; its README isn't in any
# toctree, which `-W` would otherwise turn into a hard build failure.
exclude_patterns = ['_build', 'superpowers', 'screenshots']
source_suffix = {
    '.rst': 'restructuredtext',
    '.md': 'markdown',
}
master_doc = 'index'

html_theme = 'furo'
# `../django_utils/static` serves the package's own shipped JS/CSS (the
# admin JSON widget, dropdown filter, ...) directly from the site, so the
# live demo pages load the exact files the package installs -- no copies,
# no drift. Sphinx merges multiple `html_static_path` entries into one
# `_static/` tree keyed by each entry's basename, so this adds
# `_static/django_utils/...` alongside the existing `_static/` contents
# rather than replacing them.
html_static_path = ['_static', '../django_utils/static']
# The select2 filter demo needs the admin's vendored jQuery + select2 --
# files Django ships, not this package (`Select2Mixin.Media` is what pulls
# them in on a real changelist). Same no-copies principle as above, applied
# to the installed Django: stage exactly the files the demo loads (not the
# admin's whole static tree) and let Sphinx merge them in as
# `_static/admin/...`. Staged under `_build` so nothing lands in the
# committed source tree.
_admin_static = (
    pathlib.Path(django.contrib.admin.__file__).parent / 'static' / 'admin'
)
_admin_vendor_files = [
    'js/vendor/jquery/jquery.js',
    'js/vendor/select2/select2.full.js',
    'js/jquery.init.js',
    'css/vendor/select2/select2.css',
]
_admin_vendor_stage = pathlib.Path(__file__).parent / '_build' / 'admin-vendor'
for _rel in _admin_vendor_files:
    _dest = _admin_vendor_stage / 'admin' / _rel
    _dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(_admin_static / _rel, _dest)
html_static_path.append(str(_admin_vendor_stage))
# terminal.js/.css live only in docs/_static/ (this package doesn't ship
# a terminal effect) -- registered so every page gets the typewriter
# behavior for `<pre data-terminal>` blocks (used by commands.md).
# admin-demo.css is likewise docs-only: the admin-sidebar look for the
# filter demo panels, standing in for the admin stylesheets those pages
# don't load.
html_js_files = ['terminal.js']
html_css_files = ['terminal.css', 'admin-demo.css']
