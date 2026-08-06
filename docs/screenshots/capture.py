# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "django>=5.2,<6",
#     "playwright>=1.40",
#     "python-utils>=3.5.2",
# ]
# ///
"""Capture the six admin screenshots `docs/admin.md` embeds.

Self-contained: `uv run docs/screenshots/capture.py` is the entire
interface. It builds a throwaway sqlite database in a tempdir, seeds
it (`demo_project.seed`), runs `demo_project`'s admin (wiring up this
package's JSON filters, JSON widget, read-only mixin, count columns
and export actions against `tests.test_app` models -- see
`demo_project/admin.py`) behind a real `runserver` subprocess, drives
it with Playwright, and writes the PNGs to `docs/_static/screenshots/`.

Re-run this whenever an admin-facing template, CSS or JS file in this
package changes -- see `README.md` in this directory.

Only `django`, `playwright` and `python-utils` (a runtime dependency
of `django_utils` itself) are declared above: `django_utils`,
`tests.test_app` and `demo_project` are all pure-Python, importable
straight from the repository checkout once it's on `sys.path` --
`_add_import_paths()` below does that for this process, and the
`runserver` subprocess gets the same paths via `PYTHONPATH`.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Page

SCRIPT_PATH = Path(__file__).resolve()
SCREENSHOTS_DIR = SCRIPT_PATH.parent  # docs/screenshots
REPO_ROOT = SCREENSHOTS_DIR.parent.parent
STATIC_OUT_DIR = REPO_ROOT / 'docs' / '_static' / 'screenshots'

VIEWPORT: dict[str, int] = {'width': 1280, 'height': 800}
READY_TIMEOUT_SECONDS = 30.0
POLL_INTERVAL_SECONDS = 0.1
SHUTDOWN_TIMEOUT_SECONDS = 10.0


def _add_import_paths() -> None:
    """Make `demo_project` (sibling to this script) and `django_utils`
    / `tests.test_app` (repo root) importable from source -- explicit
    rather than relying on Python's implicit script-directory
    insertion, so this keeps working if the script is ever imported
    instead of run directly."""
    for path in (SCREENSHOTS_DIR, REPO_ROOT):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


def _ensure_chromium() -> None:
    """Idempotent: `playwright install` skips browsers already
    downloaded, so this is safe (and fast) on every run."""
    subprocess.run(
        [sys.executable, '-m', 'playwright', 'install', 'chromium'],
        check=True,
    )


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def _wait_until_ready(url: str, log_path: Path, timeout: float) -> None:
    """HTTP-poll `url` until it responds, instead of guessing a fixed
    startup delay. Any HTTP status counts as ready -- a 200 from the
    login page or even a redirect both mean the server is up; only
    connection failures mean it isn't yet."""
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)  # noqa: S310
        except urllib.error.HTTPError:  # noqa: PERF203 -- polling is expected to fail until the server is up
            return  # Server answered (even with an error status).
        except (urllib.error.URLError, ConnectionError) as exc:
            last_error = exc
            time.sleep(POLL_INTERVAL_SECONDS)
        else:
            return
    log_tail = log_path.read_text(encoding='utf-8', errors='replace')[-2000:]
    raise RuntimeError(
        f'Server at {url} did not become ready within {timeout}s. '
        f'Last error: {last_error}\n--- runserver log tail ---\n{log_tail}'
    )


def _stop_server(proc: subprocess.Popen[bytes]) -> None:
    proc.terminate()
    try:
        proc.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=SHUTDOWN_TIMEOUT_SECONDS)


def _login(page: Page, base_url: str, username: str, password: str) -> None:
    page.goto(f'{base_url}/admin/login/')
    page.locator('#id_username').fill(username)
    page.locator('#id_password').fill(password)
    page.locator('#login-form input[type="submit"]').click()
    page.wait_for_url(f'{base_url}/admin/')


def _capture_filters_sidebar(page: Page, base_url: str, out_dir: Path) -> None:
    """`filters-sidebar.png`: the JSON dropdown filter on `data__filling`,
    open. Five seeded fillings (> 3) makes `dropdown_filter.js` swap the
    no-JS link list for a real `<select>`; headless Chromium never
    renders that select's native popup into a screenshot (see the
    longer note in `_capture_export_actions`), so this expands it into
    an inline listbox the same way, showing every filling choice."""
    page.goto(f'{base_url}/admin/test_app/sandwich/')
    select = page.locator('[data-dropdown-filter]')
    select.wait_for(state='visible')
    select.focus()
    select.evaluate(
        "(el) => { el.size = el.options.length; el.style.height = 'auto'; }"
    )
    page.screenshot(path=str(out_dir / 'filters-sidebar.png'))


def _capture_operator_filter(page: Page, base_url: str, out_dir: Path) -> None:
    """`operator-filter.png`: the `data__price` operator/lookup-template
    filter, pre-filled via query string so both the operator `<select>`
    (`gte`) and the value input (`550`) are visibly populated."""
    page.goto(
        f'{base_url}/admin/test_app/sandwich/'
        '?data__price=550&data__price__op=gte'
    )
    page.wait_for_selector('.lookup-filter-value')
    page.screenshot(path=str(out_dir / 'operator-filter.png'))


def _capture_json_widget(
    page: Page, base_url: str, sandwich_id: int, out_dir: Path
) -> None:
    """`json-widget.png`: the pretty-printed, multi-key JSON document
    `JSONWidget` renders, then broken via the textarea to show the
    inline validation error `json_widget.js` adds."""
    page.goto(f'{base_url}/admin/test_app/sandwich/{sandwich_id}/change/')
    textarea = page.locator('textarea[data-json-widget]')
    textarea.wait_for(state='visible')
    textarea.fill(
        '{\n  "filling": "turkey",\n  "notes": "double bacon, extra mayo",'
        '\n  "price": 650,\n  "toasted": true\n'  # missing closing brace
    )
    page.locator('.django-utils-json-error').wait_for(state='visible')
    page.screenshot(path=str(out_dir / 'json-widget.png'))


def _capture_readonly_admin(
    page: Page, base_url: str, tag_id: int, out_dir: Path
) -> None:
    """`readonly-admin.png`: a `ReadOnlyModelAdminMixin` change view --
    `name` and the `sandwiches` many-to-many both locked read-only."""
    page.goto(f'{base_url}/admin/test_app/tag/{tag_id}/change/')
    page.wait_for_selector('#content')
    page.screenshot(path=str(out_dir / 'readonly-admin.png'))


def _capture_count_columns(page: Page, base_url: str, out_dir: Path) -> None:
    """`count-columns.png`: `CountColumnMixin`'s `review_count` /
    `topping_count` columns, sorted descending by `review_count`
    (`list_display` is `id, filling, price, review_count,
    topping_count` -- 1-based index 4, `?o=-4`)."""
    page.goto(f'{base_url}/admin/test_app/sandwich/?o=-4')
    page.wait_for_selector('#result_list')
    page.screenshot(path=str(out_dir / 'count-columns.png'))


def _capture_export_actions(page: Page, base_url: str, out_dir: Path) -> None:
    """`export-actions.png`: the changelist action `<select>` open,
    showing both `ExportMixin` actions (CSV and JSON).

    Headless Chromium doesn't render a native `<select>` popup into a
    page screenshot at all -- it's composited outside the page surface
    Playwright captures, a long-standing headless limitation, not
    something a click-then-wait can work around. Setting the *same*
    `<select>` element's `size` to its option count is the standard
    workaround: it turns the exact same DOM element/options into an
    inline listbox, which *is* part of the page and does get
    captured -- an honest rendering of "both actions are options on
    this control", not a fabricated look-alike."""
    page.goto(f'{base_url}/admin/test_app/ingredient/')
    page.wait_for_selector('#result_list')
    page.locator('#action-toggle').check()
    action_select = page.locator('select[name="action"]')
    # No `.click()` here: opening the native picker first leaves it in
    # a state where the `size` change below doesn't visibly render as
    # a listbox (observed empirically -- the two don't compose).
    # `.focus()` alone gives the same visual focus ring a real user's
    # click would, without the non-rendering popup.
    action_select.focus()
    # Django's admin CSS fixes `select { height: 1.875rem }` -- enough
    # for one row -- and only relaxes it back to `auto` for
    # `select[multiple]`. Setting `size` alone therefore still renders
    # a single clipped row; the inline `style.height` override below
    # (higher specificity than the stylesheet rule) is what actually
    # makes every option visible.
    action_select.evaluate(
        "(el) => { el.size = el.options.length; el.style.height = 'auto'; }"
    )
    page.screenshot(path=str(out_dir / 'export-actions.png'))


def main() -> None:
    _add_import_paths()
    _ensure_chromium()

    tmp_dir = Path(tempfile.mkdtemp(prefix='django-utils2-screenshots-'))
    db_path = tmp_dir / 'db.sqlite3'
    log_path = tmp_dir / 'runserver.log'

    os.environ['DJANGO_SETTINGS_MODULE'] = 'demo_project.settings'
    os.environ['DJANGO_UTILS_SCREENSHOT_DB'] = str(db_path)

    import django

    django.setup()

    from demo_project import seed as seed_module
    from django.core.management import call_command

    call_command('migrate', run_syncdb=True, verbosity=0)
    seed_result = seed_module.seed()

    port = _free_port()
    base_url = f'http://127.0.0.1:{port}'

    server_env = os.environ.copy()
    extra_paths = [str(SCREENSHOTS_DIR), str(REPO_ROOT)]
    existing_pythonpath = server_env.get('PYTHONPATH')
    if existing_pythonpath:
        extra_paths.append(existing_pythonpath)
    server_env['PYTHONPATH'] = os.pathsep.join(extra_paths)

    STATIC_OUT_DIR.mkdir(parents=True, exist_ok=True)

    with log_path.open('wb') as log_file:
        proc = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'django',
                'runserver',
                f'127.0.0.1:{port}',
                '--noreload',
                '--skip-checks',
            ],
            env=server_env,
            cwd=str(SCREENSHOTS_DIR),
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            _wait_until_ready(
                f'{base_url}/admin/login/', log_path, READY_TIMEOUT_SECONDS
            )

            from playwright.sync_api import sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                try:
                    browser_context = browser.new_context(viewport=VIEWPORT)
                    page = browser_context.new_page()
                    _login(
                        page,
                        base_url,
                        seed_module.SUPERUSER_USERNAME,
                        seed_module.SUPERUSER_PASSWORD,
                    )
                    _capture_filters_sidebar(page, base_url, STATIC_OUT_DIR)
                    _capture_operator_filter(page, base_url, STATIC_OUT_DIR)
                    _capture_json_widget(
                        page,
                        base_url,
                        seed_result['sandwich_id'],
                        STATIC_OUT_DIR,
                    )
                    _capture_readonly_admin(
                        page, base_url, seed_result['tag_id'], STATIC_OUT_DIR
                    )
                    _capture_count_columns(page, base_url, STATIC_OUT_DIR)
                    _capture_export_actions(page, base_url, STATIC_OUT_DIR)
                finally:
                    browser.close()
        finally:
            _stop_server(proc)

    with contextlib.suppress(OSError):
        shutil.rmtree(tmp_dir)

    print(f'Wrote 6 screenshots to {STATIC_OUT_DIR}')  # noqa: T201


if __name__ == '__main__':
    main()
