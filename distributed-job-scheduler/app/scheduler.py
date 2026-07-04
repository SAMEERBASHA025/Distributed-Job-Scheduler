from __future__ import annotations

import json
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .auth import iso, now_utc
from .db import row_to_dict, rows_to_dicts


TERMINAL_FAILURES = {"failed", "dead_letter"}


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def create_job(
    conn,
    project_id: int,
    queue_id: int,
    job_type: str,
    payload: dict[str, Any],
    scheduled_at: str | None = None,
    priority: int = 100,
    max_attempts: int | None = None,
    recurrence_cron: str | None = None,
    batch_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
    scheduled = scheduled_at or iso()
    status = "scheduled" if parse_iso(scheduled) > now_utc() else "queued"
    try:
        row = conn.execute(
            """
            INSERT INTO jobs(
              project_id, queue_id, type, payload_json, status, priority, max_attempts,
              scheduled_at, recurrence_cron, batch_id, idempotency_key
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            RETURNING *
            """,
            (
                project_id,
                queue_id,
                job_type,
                json.dumps(payload, separators=(",", ":")),
                status,
                priority,
                max_attempts,
                scheduled,
                recurrence_cron,
                batch_id,
                idempotency_key,
            ),
        ).fetchone()
    except Exception:
        if idempotency_key:
            row = conn.execute(
                "SELECT * FROM jobs WHERE project_id = ? AND idempotency_key = ?",
                (project_id, idempotency_key),
            ).fetchone()
            if row:
                return deserialize_job(row_to_dict(row))
        raise
    job = deserialize_job(row_to_dict(row))
    add_log(conn, job["id"], None, "info", "job created", {"status": status})
    return job


def create_batch(conn, project_id: int, queue_id: int, jobs: list[dict]) -> dict:
    batch_id = f"batch-{int(time.time() * 1000)}-{random.randint(1000,9999)}"
    created = [
        create_job(
            conn,
            project_id,
            queue_id,
            job["type"],
            job.get("payload", {}),
            job.get("scheduled_at"),
            job.get("priority", 100),
            job.get("max_attempts"),
            job.get("recurrence_cron"),
            batch_id,
            job.get("idempotency_key"),
        )
        for job in jobs
    ]
    return {"batch_id": batch_id, "jobs": created}


def materialize_due_scheduled(conn) -> int:
    rows = conn.execute(
        "UPDATE jobs SET status = 'queued', updated_at = ? WHERE status = 'scheduled' AND scheduled_at <= ? RETURNING id",
        (iso(), iso()),
    ).fetchall()
    for row in rows:
        add_log(conn, row["id"], None, "info", "scheduled job became queueable", {})
    return len(rows)


def claim_next_job(conn, worker_id: int, queue_id: int | None = None) -> dict | None:
    materialize_due_scheduled(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        params: list[Any] = [iso()]
        queue_filter = ""
        if queue_id is not None:
            queue_filter = "AND queues.id = ?"
            params.append(queue_id)
        row = conn.execute(
            f"""
            SELECT jobs.*
            FROM jobs
            JOIN queues ON queues.id = jobs.queue_id
            WHERE jobs.status = 'queued'
              AND jobs.scheduled_at <= ?
              AND queues.is_paused = 0
              {queue_filter}
              AND (
                SELECT COUNT(*)
                FROM jobs running
                WHERE running.queue_id = jobs.queue_id
                  AND running.status IN ('claimed','running')
              ) < queues.concurrency_limit
            ORDER BY queues.priority ASC, jobs.priority ASC, jobs.created_at ASC
            LIMIT 1
            """,
            params,
        ).fetchone()
        if not row:
            conn.execute("COMMIT")
            return None
        attempt_number = row["attempt_count"] + 1
        now = iso()
        conn.execute(
            """
            UPDATE jobs
            SET status = 'claimed', locked_by_worker_id = ?, claimed_at = ?, attempt_count = ?,
                updated_at = ?
            WHERE id = ? AND status = 'queued'
            """,
            (worker_id, now, attempt_number, now, row["id"]),
        )
        execution = conn.execute(
            """
            INSERT INTO job_executions(job_id, worker_id, attempt_number, status, created_at)
            VALUES (?, ?, ?, 'claimed', ?)
            RETURNING *
            """,
            (row["id"], worker_id, attempt_number, now),
        ).fetchone()
        add_log(conn, row["id"], execution["id"], "info", "job claimed", {"worker_id": worker_id})
        conn.execute("COMMIT")
        claimed = get_job(conn, row["id"])
        claimed["execution_id"] = execution["id"]
        return claimed
    except Exception:
        conn.execute("ROLLBACK")
        raise


def start_execution(conn, job_id: int, execution_id: int) -> None:
    now = iso()
    conn.execute("UPDATE jobs SET status = 'running', started_at = ?, updated_at = ? WHERE id = ?", (now, now, job_id))
    conn.execute(
        "UPDATE job_executions SET status = 'running', started_at = ? WHERE id = ?",
        (now, execution_id),
    )
    add_log(conn, job_id, execution_id, "info", "job started", {})


def finish_execution(conn, job_id: int, execution_id: int, success: bool, error: str | None = None) -> None:
    job = get_job(conn, job_id)
    now = iso()
    started = parse_iso(job["started_at"]) if job.get("started_at") else now_utc()
    duration_ms = max(0, int((now_utc() - started).total_seconds() * 1000))
    if success:
        conn.execute(
            """
            UPDATE jobs
            SET status = 'completed', completed_at = ?, updated_at = ?, locked_by_worker_id = NULL
            WHERE id = ?
            """,
            (now, now, job_id),
        )
        conn.execute(
            """
            UPDATE job_executions
            SET status = 'completed', completed_at = ?, duration_ms = ?
            WHERE id = ?
            """,
            (now, duration_ms, execution_id),
        )
        add_log(conn, job_id, execution_id, "info", "job completed", {"duration_ms": duration_ms})
        if job.get("recurrence_cron"):
            reschedule_recurring(conn, job)
        return

    retry_or_dead_letter(conn, job, execution_id, error or "job failed", duration_ms)


def retry_or_dead_letter(conn, job: dict, execution_id: int, error: str, duration_ms: int) -> None:
    now = iso()
    conn.execute(
        """
        UPDATE job_executions
        SET status = 'failed', completed_at = ?, duration_ms = ?, error_message = ?
        WHERE id = ?
        """,
        (now, duration_ms, error, execution_id),
    )
    policy = get_retry_policy_for_job(conn, job)
    max_attempts = job.get("max_attempts") or policy["max_attempts"]
    if job["attempt_count"] < max_attempts:
        delay = compute_delay(policy, job["attempt_count"])
        next_run = iso(now_utc() + timedelta(seconds=delay))
        conn.execute(
            """
            UPDATE jobs
            SET status = 'scheduled', scheduled_at = ?, last_error = ?, locked_by_worker_id = NULL, updated_at = ?
            WHERE id = ?
            """,
            (next_run, error, now, job["id"]),
        )
        conn.execute(
            """
            INSERT INTO retry_history(job_id, execution_id, attempt_number, strategy, delay_seconds, next_run_at, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (job["id"], execution_id, job["attempt_count"], policy["strategy"], delay, next_run, error),
        )
        add_log(conn, job["id"], execution_id, "warning", "job scheduled for retry", {"next_run_at": next_run, "error": error})
        return

    conn.execute(
        """
        UPDATE jobs
        SET status = 'dead_letter', completed_at = ?, last_error = ?, locked_by_worker_id = NULL, updated_at = ?
        WHERE id = ?
        """,
        (now, error, now, job["id"]),
    )
    conn.execute(
        """
        INSERT OR IGNORE INTO dead_letter_queue(job_id, queue_id, failed_execution_id, reason, payload_snapshot_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (job["id"], job["queue_id"], execution_id, error, json.dumps(job["payload"])),
    )
    add_log(conn, job["id"], execution_id, "error", "job moved to dead letter queue", {"error": error})


def retry_dead_letter(conn, job_id: int) -> dict:
    job = get_job(conn, job_id)
    if not job or job["status"] != "dead_letter":
        raise ValueError("job is not in dead letter queue")
    now = iso()
    conn.execute("DELETE FROM dead_letter_queue WHERE job_id = ?", (job_id,))
    conn.execute(
        """
        UPDATE jobs
        SET status = 'queued', scheduled_at = ?, locked_by_worker_id = NULL, completed_at = NULL, updated_at = ?
        WHERE id = ?
        """,
        (now, now, job_id),
    )
    add_log(conn, job_id, None, "info", "dead letter job manually retried", {})
    return get_job(conn, job_id)


def compute_delay(policy: dict, attempt_count: int) -> int:
    base = policy["base_delay_seconds"]
    cap = policy["max_delay_seconds"]
    if policy["strategy"] == "fixed":
        delay = base
    elif policy["strategy"] == "linear":
        delay = base * attempt_count
    else:
        delay = base * (2 ** max(0, attempt_count - 1))
    return min(cap, max(0, delay))


def get_retry_policy_for_job(conn, job: dict) -> dict:
    row = conn.execute(
        """
        SELECT retry_policies.*
        FROM queues
        LEFT JOIN retry_policies ON retry_policies.id = queues.retry_policy_id
        WHERE queues.id = ?
        """,
        (job["queue_id"],),
    ).fetchone()
    policy = row_to_dict(row)
    if not policy or policy.get("id") is None:
        return {"strategy": "exponential", "max_attempts": 3, "base_delay_seconds": 5, "max_delay_seconds": 300}
    return policy


def register_worker(conn, name: str, concurrency: int) -> dict:
    now = iso()
    conn.execute(
        """
        INSERT INTO workers(name, status, concurrency, started_at, last_heartbeat_at)
        VALUES (?, 'online', ?, ?, ?)
        ON CONFLICT(name) DO UPDATE SET
          status = 'online',
          concurrency = excluded.concurrency,
          started_at = excluded.started_at,
          last_heartbeat_at = excluded.last_heartbeat_at,
          stopped_at = NULL
        """,
        (name, concurrency, now, now),
    )
    return row_to_dict(conn.execute("SELECT * FROM workers WHERE name = ?", (name,)).fetchone())


def heartbeat(conn, worker_id: int, active_jobs: int, status: str = "online") -> None:
    now = iso()
    conn.execute(
        "UPDATE workers SET status = ?, last_heartbeat_at = ? WHERE id = ?",
        (status, now, worker_id),
    )
    conn.execute(
        "INSERT INTO worker_heartbeats(worker_id, active_jobs, status, created_at) VALUES (?, ?, ?, ?)",
        (worker_id, active_jobs, status, now),
    )


def stop_worker(conn, worker_id: int) -> None:
    now = iso()
    conn.execute(
        "UPDATE workers SET status = 'offline', stopped_at = ?, last_heartbeat_at = ? WHERE id = ?",
        (now, now, worker_id),
    )


def add_log(conn, job_id: int, execution_id: int | None, level: str, message: str, context: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO job_logs(job_id, execution_id, level, message, context_json) VALUES (?, ?, ?, ?, ?)",
        (job_id, execution_id, level, message, json.dumps(context or {}, separators=(",", ":"))),
    )


def get_job(conn, job_id: int) -> dict:
    return deserialize_job(row_to_dict(conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()))


def list_jobs(conn, project_id: int, status: str | None, queue_id: int | None, limit: int, offset: int) -> list[dict]:
    clauses = ["project_id = ?"]
    params: list[Any] = [project_id]
    if status:
        clauses.append("status = ?")
        params.append(status)
    if queue_id:
        clauses.append("queue_id = ?")
        params.append(queue_id)
    params.extend([limit, offset])
    rows = conn.execute(
        f"SELECT * FROM jobs WHERE {' AND '.join(clauses)} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params,
    ).fetchall()
    return [deserialize_job(row_to_dict(row)) for row in rows]


def queue_stats(conn, project_id: int) -> list[dict]:
    rows = conn.execute(
        """
        SELECT
          queues.*,
          SUM(CASE WHEN jobs.status = 'queued' THEN 1 ELSE 0 END) AS queued,
          SUM(CASE WHEN jobs.status = 'running' THEN 1 ELSE 0 END) AS running,
          SUM(CASE WHEN jobs.status = 'completed' THEN 1 ELSE 0 END) AS completed,
          SUM(CASE WHEN jobs.status = 'dead_letter' THEN 1 ELSE 0 END) AS dead_letter
        FROM queues
        LEFT JOIN jobs ON jobs.queue_id = queues.id
        WHERE queues.project_id = ?
        GROUP BY queues.id
        ORDER BY queues.priority ASC, queues.name ASC
        """,
        (project_id,),
    ).fetchall()
    return rows_to_dicts(rows)


def system_health(conn, project_id: int) -> dict:
    stats = conn.execute(
        """
        SELECT status, COUNT(*) AS count
        FROM jobs
        WHERE project_id = ?
        GROUP BY status
        """,
        (project_id,),
    ).fetchall()
    workers = rows_to_dicts(conn.execute("SELECT * FROM workers ORDER BY last_heartbeat_at DESC").fetchall())
    return {
        "jobs": {row["status"]: row["count"] for row in stats},
        "workers": workers,
        "queues": queue_stats(conn, project_id),
    }


def reschedule_recurring(conn, job: dict) -> None:
    next_run = next_cron_run(job["recurrence_cron"])
    create_job(
        conn,
        job["project_id"],
        job["queue_id"],
        job["type"],
        job["payload"],
        next_run,
        job["priority"],
        job.get("max_attempts"),
        job.get("recurrence_cron"),
    )


def next_cron_run(expr: str) -> str:
    parts = expr.split()
    if len(parts) != 5 or not parts[0].startswith("*/"):
        return iso(now_utc() + timedelta(minutes=5))
    try:
        minutes = max(1, int(parts[0].removeprefix("*/")))
    except ValueError:
        minutes = 5
    return iso(now_utc() + timedelta(minutes=minutes))


def deserialize_job(job: dict | None) -> dict:
    if not job:
        return {}
    job["payload"] = json.loads(job.pop("payload_json"))
    return job
