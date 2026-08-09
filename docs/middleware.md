# Middleware & context

Request-scoped helpers that stay correct under both WSGI and ASGI:
contextvars-based current request/user access, header-based CSRF
hardening via `Sec-Fetch-Site`, view decorators for superuser/staff
checks, and production-safe query budgets that catch N+1 regressions
outside of tests.

(current-request-user)=

## Current request / user (ASGI-safe)

Store the current request and user in contextvars for access from
anywhere without needing to pass them as function arguments. Unlike
thread-local equivalents like `django-crum`, which leak state between
interleaved requests under ASGI, `RequestContextMiddleware` uses
`contextvars.ContextVar`. A `ContextVar` is isolated per asyncio task
and safe under both WSGI and ASGI.

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django_utils.context.RequestContextMiddleware',
]
```

```python
from django_utils.context import get_current_request, get_current_user

class MyModel(models.Model):
    def save(self, *args, **kwargs):
        user = get_current_user()
        # `get_current_user()` returns the real `AnonymousUser` instance
        # (which is truthy!) for anonymous requests, so check
        # `is_authenticated`, not just `if user:`.
        if user is not None and user.is_authenticated:
            self.updated_by = user
        super().save(*args, **kwargs)
```

For tests and management commands, use the `current_request()` context
manager instead of adding the middleware. It nests, restoring the
previous request on exit.

::::{tab-set}

:::{tab-item} Sync (WSGI)
Under WSGI, each request runs on its own OS thread. A thread-local
would already isolate requests correctly here. `ContextVar` works
just as well, and keeps the same code correct if the project ever
moves to ASGI.
:::

:::{tab-item} Async (ASGI)
Under ASGI, a single thread's event loop interleaves many requests as
concurrent asyncio tasks, so a thread-local leaks state between them.
`contextvars.ContextVar` is isolated per asyncio task, and is
propagated into `sync_to_async` threads by `asgiref`, which is what
lets synchronous helper code (a model's `save()`, a signal handler)
keep seeing the right request/user even when called from an async
view via `sync_to_async`.
:::

::::

:::{dropdown} Caveat: StreamingHttpResponse body context
The context variable is reset in a `finally` as soon as the view
returns a response, *before* a `StreamingHttpResponse` body iterator
runs. `get_current_request()` called from inside a streaming
response's body generator therefore returns `None`, not the request
that triggered it.
:::

API reference: {py:class}`~django_utils.context.RequestContextMiddleware`,
{py:func}`~django_utils.context.get_current_request`,
{py:func}`~django_utils.context.current_request`.

## Fetch-Metadata CSRF middleware

Modern browsers send request metadata headers that let you reject
cross-site state-changing requests before token checks even run, as a
second layer, not a replacement. The `Sec-Fetch-Site` header (sent by
all modern browsers since roughly 2019) tells you whether a request
is same-origin, same-site, or cross-site, with no tokens required.

`FetchMetadataMiddleware` rejects cross-site state-changing requests
by header inspection alone, with a fallback to the `Origin` header for
older browsers. It's **defense-in-depth**: run it *alongside* Django's
`CsrfViewMiddleware`, never instead of it. Old browsers and
non-browser clients (curl, webhooks) carry neither header and pass
through. That is where token CSRF still catches attacks.

The policy, in order:

1. Safe methods (GET/HEAD/OPTIONS/TRACE) always pass.
2. Views marked `@fetch_metadata_exempt` pass.
3. `Sec-Fetch-Site` present: allow `same-origin`/`same-site`/`none`
   (browser UI) and reject everything else with 403. Unknown values
   fail closed.
4. No `Sec-Fetch-Site`: compare the `Origin` header to `scheme://host`
   and reject a mismatch.
5. Neither header: allow (token CSRF is the backstop).

```python
MIDDLEWARE = [
    # ... other middleware ...
    'django_utils.middleware.FetchMetadataMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',  # Keep this
]
```

```python
from django_utils.middleware import fetch_metadata_exempt

@fetch_metadata_exempt
def webhook_view(request):
    # This view accepts cross-site requests (e.g., GitHub webhooks)
    return HttpResponse('ok')
```

:::{dropdown} Caveat: SECURE_PROXY_SSL_HEADER and step 4
Behind a TLS-terminating proxy without `SECURE_PROXY_SSL_HEADER`
configured, step 4 can false-reject a legacy browser: `request.scheme`
reads `http` while its `Origin` header is `https://...`, so the
exact-match comparison fails and the request is rejected as
cross-site. Modern browsers are unaffected, because they send
`Sec-Fetch-Site`, which step 3 handles first. Configure
`SECURE_PROXY_SSL_HEADER` per
[the Django docs](https://docs.djangoproject.com/en/stable/ref/settings/#secure-proxy-ssl-header)
to fix `request.scheme` itself.
:::

References: [django/new-features #98](https://github.com/django/new-features/issues/98),
[Go's approach](https://pkg.go.dev/net/http#CrossOriginProtection).

API reference: {py:class}`~django_utils.middleware.FetchMetadataMiddleware`,
{py:func}`~django_utils.middleware.fetch_metadata_exempt`.

## Auth helpers

Permission checks and decorator helpers for view access control.
Django ships `login_required` and `permission_required`, but
`superuser_required` and `staff_required` must be reimplemented in
nearly every project. Likewise, building permission strings for
`user.has_perm()` is always hand-formatted. Both decorators work on
sync and async views alike.

```python
from django_utils.auth import superuser_required, staff_required, permission_string

# Decorate views to require superuser (bare or with options)
@superuser_required
def admin_only_view(request):
    return HttpResponse('Admin content')

@superuser_required(raise_exception=True)  # Raises 403 instead of redirecting
def strict_admin_view(request):
    return HttpResponse('Admin content')

# Same for staff
@staff_required
def staff_only_view(request):
    return HttpResponse('Staff content')

# Build permission strings for has_perm checks
if user.has_perm(permission_string(MyModel, 'change')):
    # user can change MyModel instances
    pass
```

API reference: {py:func}`~django_utils.auth.superuser_required`,
{py:func}`~django_utils.auth.staff_required`,
{py:func}`~django_utils.auth.permission_string`.

(query-budgets)=

## Query budgets

Catch N+1 regressions in production code paths, not just in tests or
behind a development-only debug toolbar.

`django_utils.query_debug.query_budget` counts every query a block
executes and logs a warning or raises an exception when the block
exceeds its budget. It's production-safe by construction: counting
uses Django's `connection.execute_wrapper()` (public API, active
regardless of `DEBUG`) instead of accumulating `connection.queries`
logs which leak memory in long-lived processes.

Usable as a context manager or a decorator:

```python
from django_utils.query_debug import query_budget

# Warn past 20 queries, raise past 100
with query_budget(warn_at=20, raise_at=100):
    results = expensive_operation()

# Decorator form: fresh budget per call
@query_budget(warn_at=10)
def my_view(request):
    return render(request, 'template.html', expensive_context())
```

`using` limits counting to one connection alias. The default counts
every configured connection. Exceeding `raise_at` raises
`QueryBudgetExceeded` from the first over-budget query, carrying the
query count and the offending SQL. Construction itself validates:
`ValueError` if neither `warn_at` nor `raise_at` is given, if either
is below 1, or if `warn_at` is above `raise_at` (which could never
warn).

:::{dropdown} Caveat: thread-safety and reentrancy
`query_budget` instances are single-use per `with` block (not
reentrant). Entering the same instance twice raises `RuntimeError`.
The decorator form is safe because each decorated call gets a fresh
instance internally, but instances themselves are **not thread-safe**:
don't share one `query_budget` instance across threads.
:::

API reference: {py:class}`~django_utils.query_debug.query_budget`,
{py:class}`~django_utils.query_debug.QueryBudgetExceeded`.
