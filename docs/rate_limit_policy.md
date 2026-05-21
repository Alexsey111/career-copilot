# Rate Limit Policy

## Purpose

Rate limiting protects risky endpoints from abuse, accidental loops, brute force attempts, upload spam, and uncontrolled pilot usage.

Current implementation is intentionally simple and suitable for a single-node pilot deployment.

---

## Current implementation

The backend uses an in-memory fixed window limiter.

Limit state is process-local.

This means:
- it works for single-node deployments;
- limits reset on process restart;
- it is not sufficient for multi-instance production;
- Redis-backed rate limiting is required before horizontal scaling.

---

## Protected endpoints

| Endpoint | Policy |
|---|---|
| `POST /api/v1/auth/login` | `auth_login` |
| `POST /api/v1/auth/password-reset/request` | `password_reset_request` |
| `POST /api/v1/files/upload` | `file_upload` |

---

## Environment variables

| Variable | Default | Meaning |
|---|---:|---|
| `RATE_LIMIT_ENABLED` | `true` | Enables/disables rate limiting |
| `RATE_LIMIT_LOGIN_LIMIT` | `10` | Login attempts per window |
| `RATE_LIMIT_LOGIN_WINDOW_SECONDS` | `60` | Login window duration |
| `RATE_LIMIT_PASSWORD_RESET_LIMIT` | `5` | Password reset requests per window |
| `RATE_LIMIT_PASSWORD_RESET_WINDOW_SECONDS` | `300` | Password reset window duration |
| `RATE_LIMIT_UPLOAD_LIMIT` | `20` | Upload requests per window |
| `RATE_LIMIT_UPLOAD_WINDOW_SECONDS` | `300` | Upload window duration |

---

## Error response

When a client exceeds a limit, the API returns:

```json
{
  "error": {
    "code": "rate_limit_exceeded",
    "message": "Too many requests",
    "correlation_id": "...",
    "details": {
      "policy": "auth_login",
      "limit": 10,
      "window_seconds": 60
    }
  }
}
```

HTTP status:

429 Too Many Requests
