from __future__ import annotations

import argparse
import json
import re
import sqlite3
from http import HTTPStatus
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .auth import authenticate_token, create_token, hash_password, verify_password
from .db import DEFAULT_DB_PATH, apply_schema, connect, row_to_dict, rows_to_dicts
from .scheduler import create_batch, create_job, list_jobs, queue_stats, retry_dead_letter, system_health

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"


class ApiError(Exception):
    def __init__(self, status: int, message: str, details: dict | None = None):
        self.status = status
        self.message = message
        self.details = details or {}


class Handler(BaseHTTPRequestHandler):
    server_version = "SchedulerHTTP/1.0"

    def do_GET(self) -> None:
        self.route()

    def do_POST(self) -> None:
        self.route()

    def do_PATCH(self) -> None:
        self.route()

    def route(self) -> None:
        try:
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/"):
                self.handle_api(parsed.path, parse_qs(parsed.query))
            else:
                self.handle_static(parsed.path)
        except ApiError as exc:
            self.json_response({"error": {"message": exc.message, "details": exc.details}}, exc.status)
        except sqlite3.IntegrityError as exc:
            self.json_response(
                {"error": {"message": friendly_integrity_error(str(exc)), "details": {"constraint": str(exc)}}},
                409,
            )
        except Exception as exc:
            self.json_response({"error": {"message": "internal server error", "details": {"exception": str(exc)}}}, 500)

    def handle_static(self, path: str) -> None:
        target = STATIC / "index.html" if path in ("", "/") else STATIC / path.lstrip("/")
        if not target.exists() or not target.is_file():
            self.send_error(404)
            return
        content_type = "text/html"
        if target.suffix == ".css":
            content_type = "text/css"
        elif target.suffix == ".js":
            content_type = "application/javascript"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def handle_api(self, path: str, query: dict) -> None:
        conn = connect(self.server.db_path)  # type: ignore[attr-defined]
        try:
            if path == "/api/auth/register" and self.command == "POST":
                body = self.read_json()
                require_fields(body, ["email", "password", "display_name", "organization_name"])
                validate_registration(body)
                user = conn.execute(
                    "INSERT INTO users(email, password_hash, display_name) VALUES (?, ?, ?) RETURNING *",
                    (body["email"].strip().lower(), hash_password(body["password"]), body["display_name"].strip()),
                ).fetchone()
                org = conn.execute(
                    "INSERT INTO organizations(name) VALUES (?) RETURNING *",
                    (body["organization_name"].strip(),),
                ).fetchone()
                conn.execute(
                    "INSERT INTO organization_members(organization_id, user_id, role) VALUES (?, ?, 'owner')",
                    (org["id"], user["id"]),
                )
                token = create_token(conn, user["id"])
                self.json_response({"token": token, "user": row_to_dict(user), "organization": row_to_dict(org)}, 201)
                return

            if path == "/api/auth/login" and self.command == "POST":
                body = self.read_json()
                require_fields(body, ["email", "password"])
                user = conn.execute("SELECT * FROM users WHERE email = ?", (body["email"].strip().lower(),)).fetchone()
                if not user or not verify_password(body["password"], user["password_hash"]):
                    raise ApiError(401, "invalid email or password")
                self.json_response({"token": create_token(conn, user["id"]), "user": public_user(row_to_dict(user))})
                return

            user = authenticate_token(conn, self.headers.get("Authorization"))
            if not user:
                raise ApiError(401, "missing or invalid bearer token")

            if path == "/api/me":
                self.json_response({"user": public_user(user), "projects": list_projects(conn, user["id"])})
                return

            parts = [p for p in path.split("/") if p]
            if len(parts) >= 2 and parts[1] == "projects":
                self.handle_project_api(conn, user, parts[2:], query)
                return
            if path == "/api/workers":
                self.json_response({"workers": rows_to_dicts(conn.execute("SELECT * FROM workers ORDER BY last_heartbeat_at DESC").fetchall())})
                return
            raise ApiError(404, "route not found")
        finally:
            conn.close()

    def handle_project_api(self, conn, user: dict, parts: list[str], query: dict) -> None:
        if not parts and self.command == "POST":
            body = self.read_json()
            require_fields(body, ["organization_id", "name", "slug"])
            ensure_member(conn, user["id"], int(body["organization_id"]))
            project = conn.execute(
                "INSERT INTO projects(organization_id, name, slug) VALUES (?, ?, ?) RETURNING *",
                (body["organization_id"], body["name"], body["slug"]),
            ).fetchone()
            default_policy = conn.execute(
                """
                INSERT INTO retry_policies(project_id, name, strategy, max_attempts, base_delay_seconds, max_delay_seconds)
                VALUES (?, 'default exponential', 'exponential', 3, 5, 300)
                RETURNING *
                """,
                (project["id"],),
            ).fetchone()
            self.json_response({"project": row_to_dict(project), "retry_policy": row_to_dict(default_policy)}, 201)
            return
        if not parts:
            self.json_response({"projects": list_projects(conn, user["id"])})
            return

        project_id = int(parts[0])
        ensure_project_access(conn, user["id"], project_id)

        if len(parts) == 1:
            self.json_response({"project": row_to_dict(conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone())})
            return

        resource = parts[1]
        if resource == "retry-policies":
            if self.command == "POST":
                body = self.read_json()
                require_fields(body, ["name", "strategy", "max_attempts", "base_delay_seconds", "max_delay_seconds"])
                policy = conn.execute(
                    """
                    INSERT INTO retry_policies(project_id, name, strategy, max_attempts, base_delay_seconds, max_delay_seconds)
                    VALUES (?, ?, ?, ?, ?, ?)
                    RETURNING *
                    """,
                    (project_id, body["name"], body["strategy"], body["max_attempts"], body["base_delay_seconds"], body["max_delay_seconds"]),
                ).fetchone()
                self.json_response({"retry_policy": row_to_dict(policy)}, 201)
                return
            self.json_response({"retry_policies": rows_to_dicts(conn.execute("SELECT * FROM retry_policies WHERE project_id = ?", (project_id,)).fetchall())})
            return

        if resource == "queues":
            self.handle_queues(conn, project_id, parts[2:])
            return
        if resource == "jobs":
            self.handle_jobs(conn, project_id, parts[2:], query)
            return
        if resource == "health":
            self.json_response(system_health(conn, project_id))
            return
        raise ApiError(404, "project route not found")

    def handle_queues(self, conn, project_id: int, parts: list[str]) -> None:
        if not parts and self.command == "POST":
            body = self.read_json()
            require_fields(body, ["name"])
            queue = conn.execute(
                """
                INSERT INTO queues(project_id, retry_policy_id, name, priority, concurrency_limit)
                VALUES (?, ?, ?, ?, ?)
                RETURNING *
                """,
                (project_id, body.get("retry_policy_id"), body["name"], body.get("priority", 100), body.get("concurrency_limit", 5)),
            ).fetchone()
            self.json_response({"queue": row_to_dict(queue)}, 201)
            return
        if not parts:
            self.json_response({"queues": queue_stats(conn, project_id)})
            return

        queue_id = int(parts[0])
        assert_queue(conn, project_id, queue_id)
        if len(parts) == 2 and parts[1] in ("pause", "resume") and self.command == "POST":
            paused = 1 if parts[1] == "pause" else 0
            conn.execute("UPDATE queues SET is_paused = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (paused, queue_id))
            self.json_response({"queue": row_to_dict(conn.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)).fetchone())})
            return
        if self.command == "PATCH":
            body = self.read_json()
            allowed = {k: body[k] for k in ("priority", "concurrency_limit", "retry_policy_id", "is_paused") if k in body}
            if not allowed:
                raise ApiError(400, "no queue fields to update")
            assignments = ", ".join(f"{field} = ?" for field in allowed)
            conn.execute(f"UPDATE queues SET {assignments}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", [*allowed.values(), queue_id])
            self.json_response({"queue": row_to_dict(conn.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)).fetchone())})
            return
        self.json_response({"queue": row_to_dict(conn.execute("SELECT * FROM queues WHERE id = ?", (queue_id,)).fetchone())})

    def handle_jobs(self, conn, project_id: int, parts: list[str], query: dict) -> None:
        if not parts and self.command == "POST":
            body = self.read_json()
            require_fields(body, ["queue_id", "type", "payload"])
            assert_queue(conn, project_id, int(body["queue_id"]))
            job = create_job(
                conn,
                project_id,
                int(body["queue_id"]),
                body["type"],
                body.get("payload", {}),
                body.get("scheduled_at"),
                body.get("priority", 100),
                body.get("max_attempts"),
                body.get("recurrence_cron"),
                body.get("batch_id"),
                body.get("idempotency_key"),
            )
            self.json_response({"job": job}, 201)
            return
        if not parts:
            jobs = list_jobs(
                conn,
                project_id,
                first(query, "status"),
                int(first(query, "queue_id")) if first(query, "queue_id") else None,
                int(first(query, "limit") or 50),
                int(first(query, "offset") or 0),
            )
            self.json_response({"jobs": jobs})
            return
        if parts[0] == "batch" and self.command == "POST":
            body = self.read_json()
            require_fields(body, ["queue_id", "jobs"])
            assert_queue(conn, project_id, int(body["queue_id"]))
            self.json_response(create_batch(conn, project_id, int(body["queue_id"]), body["jobs"]), 201)
            return

        job_id = int(parts[0])
        job = conn.execute("SELECT * FROM jobs WHERE id = ? AND project_id = ?", (job_id, project_id)).fetchone()
        if not job:
            raise ApiError(404, "job not found")
        if len(parts) == 2 and parts[1] == "retry" and self.command == "POST":
            self.json_response({"job": retry_dead_letter(conn, job_id)})
            return
        if len(parts) == 2 and parts[1] == "logs":
            rows = conn.execute("SELECT * FROM job_logs WHERE job_id = ? ORDER BY created_at ASC", (job_id,)).fetchall()
            self.json_response({"logs": rows_to_dicts(rows)})
            return
        from .scheduler import deserialize_job
        self.json_response({"job": deserialize_job(row_to_dict(job))})

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length == 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError as exc:
            raise ApiError(400, "invalid json", {"error": str(exc)})

    def json_response(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def require_fields(body: dict, fields: list[str]) -> None:
    missing = [field for field in fields if field not in body]
    if missing:
        raise ApiError(400, "missing required fields", {"missing": missing})
    blank = [field for field in fields if isinstance(body.get(field), str) and not body[field].strip()]
    if blank:
        raise ApiError(400, "required fields cannot be blank", {"blank": blank})


def validate_registration(body: dict) -> None:
    email = body["email"].strip().lower()
    if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
        raise ApiError(400, "enter a valid email address")
    if len(body["password"]) < 6:
        raise ApiError(400, "password must be at least 6 characters")
    if len(body["display_name"].strip()) < 2:
        raise ApiError(400, "display name must be at least 2 characters")
    if len(body["organization_name"].strip()) < 2:
        raise ApiError(400, "organization name must be at least 2 characters")


def friendly_integrity_error(message: str) -> str:
    if "users.email" in message:
        return "email already registered. Use Sign in, or choose a different email."
    if "projects.organization_id, projects.slug" in message:
        return "project slug already exists for this organization."
    if "queues.project_id, queues.name" in message:
        return "queue name already exists in this project."
    if "retry_policies.project_id, retry_policies.name" in message:
        return "retry policy name already exists in this project."
    return "request conflicts with an existing record"


def public_user(user: dict) -> dict:
    user.pop("password_hash", None)
    return user


def first(query: dict, key: str) -> str | None:
    values = query.get(key)
    return values[0] if values else None


def ensure_member(conn, user_id: int, organization_id: int) -> None:
    row = conn.execute(
        "SELECT 1 FROM organization_members WHERE user_id = ? AND organization_id = ?",
        (user_id, organization_id),
    ).fetchone()
    if not row:
        raise ApiError(403, "organization access denied")


def ensure_project_access(conn, user_id: int, project_id: int) -> None:
    row = conn.execute(
        """
        SELECT 1
        FROM projects
        JOIN organization_members ON organization_members.organization_id = projects.organization_id
        WHERE projects.id = ? AND organization_members.user_id = ?
        """,
        (project_id, user_id),
    ).fetchone()
    if not row:
        raise ApiError(403, "project access denied")


def assert_queue(conn, project_id: int, queue_id: int) -> None:
    if not conn.execute("SELECT 1 FROM queues WHERE id = ? AND project_id = ?", (queue_id, project_id)).fetchone():
        raise ApiError(404, "queue not found")


def list_projects(conn, user_id: int) -> list[dict]:
    return rows_to_dicts(
        conn.execute(
            """
            SELECT projects.*
            FROM projects
            JOIN organization_members ON organization_members.organization_id = projects.organization_id
            WHERE organization_members.user_id = ?
            ORDER BY projects.created_at DESC
            """,
            (user_id,),
        ).fetchall()
    )


def seed(conn) -> None:
    if conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()["c"]:
        return
    user = conn.execute(
        "INSERT INTO users(email, password_hash, display_name) VALUES (?, ?, ?) RETURNING *",
        ("demo@example.com", hash_password("demo-password"), "Demo User"),
    ).fetchone()
    org = conn.execute("INSERT INTO organizations(name) VALUES ('Demo Org') RETURNING *").fetchone()
    conn.execute("INSERT INTO organization_members(organization_id, user_id, role) VALUES (?, ?, 'owner')", (org["id"], user["id"]))
    project = conn.execute("INSERT INTO projects(organization_id, name, slug) VALUES (?, 'Scheduler Demo', 'scheduler-demo') RETURNING *", (org["id"],)).fetchone()
    policy = conn.execute(
        """
        INSERT INTO retry_policies(project_id, name, strategy, max_attempts, base_delay_seconds, max_delay_seconds)
        VALUES (?, 'default exponential', 'exponential', 3, 3, 60)
        RETURNING *
        """,
        (project["id"],),
    ).fetchone()
    queue = conn.execute(
        "INSERT INTO queues(project_id, retry_policy_id, name, priority, concurrency_limit) VALUES (?, ?, 'emails', 10, 3) RETURNING *",
        (project["id"], policy["id"]),
    ).fetchone()
    create_job(conn, project["id"], queue["id"], "send_email", {"to": "customer@example.com", "template": "welcome"}, priority=10)
    create_job(conn, project["id"], queue["id"], "generate_invoice", {"invoice_id": 42}, priority=20)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--init-db", action="store_true")
    parser.add_argument("--seed", action="store_true")
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    conn = connect(args.db)
    if args.init_db:
        apply_schema(conn)
    if args.seed:
        seed(conn)
    conn.close()
    if args.serve:
        server = ThreadingHTTPServer((args.host, args.port), Handler)
        server.db_path = args.db  # type: ignore[attr-defined]
        print(f"serving on http://{args.host}:{args.port}")
        server.serve_forever()


if __name__ == "__main__":
    main()
