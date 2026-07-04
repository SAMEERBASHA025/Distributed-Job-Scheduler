# Design Decisions

## Relational Source of Truth

The scheduler keeps job state, queue config, retry policy, executions, logs, and workers in normalized relational tables. This makes lifecycle transitions auditable and gives the dashboard efficient filters. Payloads remain JSON because each job type owns its own business shape.

## Atomic Claiming

Job claiming uses a transaction that materializes due scheduled jobs, checks paused queue state and queue concurrency, picks the highest-priority eligible job, marks it `claimed`, and inserts a `job_executions` row. The transaction boundary is the reliability core: a worker either owns a job with an execution record or owns nothing.

## Retry and DLQ

Retry strategy is queue-level by default and can be overridden per job with `max_attempts`. Retry history is append-only so operators can reconstruct why a job delayed, how long it waited, and which execution failed. Exhausted jobs move to `dead_letter` and receive a DLQ row with a payload snapshot.

## Idempotency

The API supports project-scoped `idempotency_key` on jobs. Duplicate submissions return the existing job instead of creating more work. Worker execution is represented with attempts and logs so job handlers can be written idempotently around external IDs.

## Worker Model

Workers poll instead of receiving pushes. Polling is simple, testable, and resilient for an assignment. Each worker has local concurrency, heartbeats, and graceful draining. A production version could replace polling with notifications, Kafka, SQS, or PostgreSQL LISTEN/NOTIFY.

## SQLite Trade-off

SQLite keeps setup friction near zero and still demonstrates the concurrency boundaries. For high-scale production, move to PostgreSQL and use `FOR UPDATE SKIP LOCKED`, partition jobs by queue or tenant, archive old executions/logs, and use read replicas for dashboards.

## Dashboard Updates

The dashboard uses polling every two seconds. This satisfies live observability without extra infrastructure. WebSockets would be a natural upgrade for lower-latency worker status, throughput charts, and log streaming.
