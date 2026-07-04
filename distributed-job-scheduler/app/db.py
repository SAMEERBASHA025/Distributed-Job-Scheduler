from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

DEFAULT_DB_PATH = Path(__file__).resolve().parents[1] / "scheduler.db"


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def apply_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def row_to_dict(row: sqlite3.Row | None) -> dict | None:
    return None if row is None else {key: row[key] for key in row.keys()}


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict]:
    return [row_to_dict(row) for row in rows]  # type: ignore[list-item]


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS auth_tokens (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS organizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS organization_members (
  organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK(role IN ('owner','admin','developer','viewer')),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (organization_id, user_id)
);

CREATE TABLE IF NOT EXISTS projects (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  slug TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (organization_id, slug)
);

CREATE TABLE IF NOT EXISTS retry_policies (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  strategy TEXT NOT NULL CHECK(strategy IN ('fixed','linear','exponential')),
  max_attempts INTEGER NOT NULL CHECK(max_attempts >= 1),
  base_delay_seconds INTEGER NOT NULL CHECK(base_delay_seconds >= 0),
  max_delay_seconds INTEGER NOT NULL CHECK(max_delay_seconds >= 0),
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS queues (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  retry_policy_id INTEGER REFERENCES retry_policies(id) ON DELETE SET NULL,
  name TEXT NOT NULL,
  priority INTEGER NOT NULL DEFAULT 100,
  concurrency_limit INTEGER NOT NULL DEFAULT 5 CHECK(concurrency_limit >= 1),
  is_paused INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (project_id, name)
);

CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
  external_id TEXT,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('queued','scheduled','claimed','running','completed','failed','dead_letter','cancelled')),
  priority INTEGER NOT NULL DEFAULT 100,
  max_attempts INTEGER,
  attempt_count INTEGER NOT NULL DEFAULT 0,
  scheduled_at TEXT NOT NULL,
  claimed_at TEXT,
  started_at TEXT,
  completed_at TEXT,
  next_run_at TEXT,
  recurrence_cron TEXT,
  batch_id TEXT,
  idempotency_key TEXT,
  last_error TEXT,
  locked_by_worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE (project_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS job_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  worker_id INTEGER REFERENCES workers(id) ON DELETE SET NULL,
  attempt_number INTEGER NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('claimed','running','completed','failed')),
  started_at TEXT,
  completed_at TEXT,
  duration_ms INTEGER,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS retry_history (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  execution_id INTEGER REFERENCES job_executions(id) ON DELETE SET NULL,
  attempt_number INTEGER NOT NULL,
  strategy TEXT NOT NULL,
  delay_seconds INTEGER NOT NULL,
  next_run_at TEXT NOT NULL,
  error_message TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS workers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  status TEXT NOT NULL CHECK(status IN ('starting','online','draining','offline')),
  concurrency INTEGER NOT NULL DEFAULT 4,
  started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_heartbeat_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
  stopped_at TEXT
);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
  active_jobs INTEGER NOT NULL,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS job_logs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
  execution_id INTEGER REFERENCES job_executions(id) ON DELETE SET NULL,
  level TEXT NOT NULL CHECK(level IN ('debug','info','warning','error')),
  message TEXT NOT NULL,
  context_json TEXT,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scheduled_jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
  queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
  job_template_json TEXT NOT NULL,
  cron_expression TEXT NOT NULL,
  next_run_at TEXT NOT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS dead_letter_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
  queue_id INTEGER NOT NULL REFERENCES queues(id) ON DELETE CASCADE,
  failed_execution_id INTEGER REFERENCES job_executions(id) ON DELETE SET NULL,
  reason TEXT NOT NULL,
  payload_snapshot_json TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jobs_claimable
  ON jobs(queue_id, status, scheduled_at, priority, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_project_status
  ON jobs(project_id, status, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_worker
  ON jobs(locked_by_worker_id, status);
CREATE INDEX IF NOT EXISTS idx_executions_job
  ON job_executions(job_id, attempt_number);
CREATE INDEX IF NOT EXISTS idx_logs_job_time
  ON job_logs(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_workers_status_heartbeat
  ON workers(status, last_heartbeat_at);
CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_next
  ON scheduled_jobs(is_active, next_run_at);
"""
