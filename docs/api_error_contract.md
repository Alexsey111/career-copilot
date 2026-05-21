# API Error Contract

All API errors follow a unified envelope:

```json
{
  "error": {
    "code": "source_file_not_found",
    "message": "Source file not found",
    "correlation_id": "...",
    "details": {}
  }
}
```

## Compatibility note

A top-level `detail` field may still exist temporarily for backward compatibility.

Clients should migrate to:
- `error.code`
- `error.message`
- `error.details`

## Stable error codes

### Authentication

| Code | Meaning |
|---|---|
| `unauthorized` | Missing or invalid auth |
| `forbidden` | Access denied |

### File upload

| Code | Meaning |
|---|---|
| `invalid_file_kind` | Unsupported file kind |
| `unsupported_file_extension` | File extension rejected |
| `unsupported_content_type` | MIME type rejected |
| `empty_upload_file` | Empty upload |
| `upload_file_too_large` | File exceeds size limit |
| `source_file_not_found` | File not found |

### Validation

| Code | Meaning |
|---|---|
| `validation_error` | Request validation failed |
| `rate_limit_exceeded` | Too many requests for this endpoint/window |

### Internal

| Code | Meaning |
|---|---|
| `internal_server_error` | Unexpected backend failure |

## Retry guidance

Retryable:
- `internal_server_error`
- temporary infrastructure/network failures

Non-retryable:
- `validation_error`
- `unsupported_file_extension`
- `unauthorized`

## Correlation ID

All responses may contain:
- `X-Correlation-ID`
- `X-Trace-ID`

These identifiers should be included in support/debug reports.
