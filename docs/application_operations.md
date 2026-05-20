# Application Operations

## Scope
Tracking, analytics, reminders. No auto-apply.

## Data sources
ApplicationRecord is source of truth for summary analytics.
ApplicationEvent is activity log/timeline.

## Status workflow
draft → ready → applied → screening/interview → offer/rejected/withdrawn

## Analytics v1
- total_applications
- count_by_status
- created_per_day
- applied_per_day
- conversion_to_applied
- offers_count
- rejections_count
- average_time_to_apply_hours

## Reminders v1
- draft_stale: draft older than 14 days
- ready_not_submitted: ready older than 7 days
- follow_up_missing: applied older than 14 days

## Product boundary
Reminders are advisory.
No background sending.
No automatic follow-up.
No external platform actions.

## Next candidates
- configurable thresholds
- dismissed reminders
- follow-up notes
- reminder severity
