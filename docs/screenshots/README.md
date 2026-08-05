# Admin screenshots

Generates the six PNGs `docs/admin.md` embeds
(`docs/_static/screenshots/*.png`) from a real, throwaway Django admin
site -- not hand-drawn mockups, the actual rendered pages.

## Running it

```sh
uv run docs/screenshots/capture.py
```

That's the whole interface. `uv run` reads the `# /// script` header
at the top of `capture.py` and builds an isolated environment for
`django`, `playwright` and `python-utils` on its own -- no prior `uv
sync` / `pip install` step needed, and no dependency on the rest of
this repo's dev environment.

**First run only**: Playwright needs its own Chromium build, which
`capture.py` downloads automatically (`python -m playwright install
chromium`, idempotent -- skipped on later runs once it's cached). That
first download is a few hundred MB and needs network access; every
run after that is fast and offline.

The script builds a demo Django project (`demo_project/`, wired to
`tests.test_app`'s models and this package's admin filters/widgets/
mixins/export actions -- see `demo_project/admin.py`), seeds it
(`demo_project/seed.py`), serves it via `runserver` in a subprocess on
a free port, drives it with Playwright, writes the six PNGs, and tears
everything down (`runserver` subprocess + browser) even if a capture
fails partway through.

## When to re-run

Any time an admin-facing template, CSS or JS file in this package
changes -- `django_utils/templates/django_utils/admin/*.html`,
`django_utils/static/django_utils/admin/*.{js,css}`, or the mixins/
filters/widgets/export Python modules that change what those pages
render. Commit the regenerated PNGs alongside the change.
