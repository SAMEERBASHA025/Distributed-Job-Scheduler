# REST API

All protected endpoints require:

```http
Authorization: Bearer <token>
Content-Type: application/json
```

## Auth

`POST /api/auth/register`

```json
{"email":"me@example.com","password":"secret","display_name":"Me","organization_name":"Acme"}
```

`POST /api/auth/login`

```json
{"email":"demo@example.com","password":"demo-password"}
```

## Projects

- `GET /api/me`
- `GET /api/projects`
- `POST /api/projects`

```json
{"organization_id":1,"name":"Payments","slug":"payments"}
```

## Retry Policies

- `GET /api/projects/{project_id}/retry-policies`
- `POST /api/projects/{project_id}/retry-policies`

```json
{"name":"fast fixed","strategy":"fixed","max_attempts":3,"base_delay_seconds":10,"max_delay_seconds":60}
```

Strategies: `fixed`, `linear`, `exponential`.

## Queues

- `GET /api/projects/{project_id}/queues`
- `POST /api/projects/{project_id}/queues`
- `PATCH /api/projects/{project_id}/queues/{queue_id}`
- `POST /api/projects/{project_id}/queues/{queue_id}/pause`
- `POST /api/projects/{project_id}/queues/{queue_id}/resume`

```json
{"name":"emails","priority":10,"concurrency_limit":5,"retry_policy_id":1}
```

## Jobs

- `GET /api/projects/{project_id}/jobs?status=queued&queue_id=1&limit=50&offset=0`
- `POST /api/projects/{project_id}/jobs`
- `GET /api/projects/{project_id}/jobs/{job_id}`
- `GET /api/projects/{project_id}/jobs/{job_id}/logs`
- `POST /api/projects/{project_id}/jobs/{job_id}/retry`
- `POST /api/projects/{project_id}/jobs/batch`

Immediate job:

```json
{"queue_id":1,"type":"send_email","payload":{"to":"customer@example.com"}}
```

Delayed or scheduled job:

```json
{"queue_id":1,"type":"send_email","payload":{},"scheduled_at":"2026-07-04T12:30:00+00:00"}
```

Recurring job:

```json
{"queue_id":1,"type":"cleanup","payload":{},"recurrence_cron":"*/5 * * * *"}
```

Batch:

```json
{
  "queue_id": 1,
  "jobs": [
    {"type":"email","payload":{"to":"a@example.com"}},
    {"type":"email","payload":{"to":"b@example.com"}}
  ]
}
```

## Health

- `GET /api/projects/{project_id}/health`
- `GET /api/workers`

Errors use a structured envelope:

```json
{"error":{"message":"missing required fields","details":{"missing":["name"]}}}
```
