# Middleware & context

Request-scoped helpers that stay correct under both WSGI and ASGI:
contextvars-based current request/user access, header-based CSRF
hardening via `Sec-Fetch-Site`, view decorators for superuser/staff
checks, and production-safe query budgets that catch N+1 regressions
outside of tests.

## Current request / user (ASGI-safe)

## Fetch-Metadata CSRF middleware

## Auth helpers

## Query budgets
