# 20251212_120945-sentry-integration

## Status

Accepted

## Context

The application lacked centralized error tracking and monitoring. Production errors were difficult to diagnose without proper observability, and there was no unified way to track issues across the frontend and backend.

**Source commits:**

- 709d6a0: AUT-281 Setup sentry - server
- dfae99a: AUT-281 Setup sentry - frontend
- e16e56d: Add: Include `sentry-sdk` with `fastapi` extra in dependencies

## Decision

Integrated Sentry for error tracking across both frontend (Next.js) and backend (FastAPI):

- **Frontend**: Sentry SDK configured in Next.js for client-side error capture
- **Backend**: Sentry SDK with FastAPI extra for server-side error tracking and request tracing

This provides unified error monitoring with source maps, breadcrumbs, and performance tracing.

## Consequences

### Positive

- Centralized error tracking across full stack
- Automatic error grouping and deduplication
- Stack traces with source context
- Performance monitoring and tracing
- Alerting capabilities for production issues

### Negative

- Additional third-party dependency
- Data sent to external service (privacy consideration)
- Potential performance overhead from instrumentation

### Constraints

- Use `sentry-sdk[fastapi]` for backend (includes ASGI middleware)
- Configure source maps for meaningful frontend stack traces
- Ensure sensitive data is scrubbed before sending to Sentry
