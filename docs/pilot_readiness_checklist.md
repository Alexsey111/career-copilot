# Pilot Readiness Checklist

## Runtime safety

- [ ] `APP_ENV=prod` or `staging`
- [ ] `APP_DEBUG=false`
- [ ] `DEV_AUTH_ENABLED=false`
- [ ] production JWT secret configured
- [ ] CORS configured for frontend domain
- [ ] wildcard CORS disabled

## Storage

- [ ] `STORAGE_MODE=minio` or `s3`
- [ ] MinIO/S3 reachable
- [ ] bucket exists
- [ ] upload flow tested
- [ ] file size limits verified

## Database

- [ ] migrations applied
- [ ] DB backup strategy documented
- [ ] rollback procedure reviewed
- [ ] latest migration tested locally/staging

## Auth & security

- [ ] login flow tested
- [ ] refresh flow tested
- [ ] logout-all tested
- [ ] password reset tested
- [ ] password reset token hidden outside local/test
- [ ] rate limiting enabled

## Observability

- [ ] request logs visible
- [ ] correlation ids present
- [ ] Sentry configured
- [ ] health endpoint reachable

## AI runtime

- [ ] AI provider credentials configured
- [ ] timeout settings verified
- [ ] retry policy verified
- [ ] document generation smoke-tested

## Core product flows

- [ ] vacancy ingestion works
- [ ] profile ingestion works
- [ ] tailored resume generation works
- [ ] cover letter generation works
- [ ] review workspace works
- [ ] application tracking works
- [ ] interview prep works

## Product safety boundaries

- [ ] no fake achievements generation
- [ ] no hidden auto-apply
- [ ] no stored HH credentials
- [ ] human review required before submission
- [ ] evidence-first workflow preserved

## Final go-live check

- [ ] smoke tests passed
- [ ] pytest suite green
- [ ] deployment runbook reviewed
- [ ] migration checklist reviewed
- [ ] rollback plan verified
- [ ] pilot contact/support process defined
