import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from app.db import apply_schema, connect
from app.main import Handler, seed


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "api-test.db"
        conn = connect(self.db_path)
        apply_schema(conn)
        seed(conn)
        conn.close()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.db_path = str(self.db_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, payload=None, token=None):
        data = json.dumps(payload or {}).encode()
        req = urllib.request.Request(
            self.base_url + path,
            data=data if method in {"POST", "PATCH"} else None,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        if token:
            req.add_header("Authorization", f"Bearer {token}")
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read().decode())

    def test_signup_creates_account_without_internal_server_error(self):
        status, body = self.request(
            "POST",
            "/api/auth/register",
            {
                "email": "student@example.com",
                "password": "student123",
                "display_name": "Student User",
                "organization_name": "Student Org",
            },
        )

        self.assertEqual(status, 201)
        self.assertIn("token", body)
        self.assertEqual(body["user"]["email"], "student@example.com")

    def test_duplicate_signup_returns_clean_conflict(self):
        payload = {
            "email": "student@example.com",
            "password": "student123",
            "display_name": "Student User",
            "organization_name": "Student Org",
        }
        self.request("POST", "/api/auth/register", payload)
        status, body = self.request("POST", "/api/auth/register", payload)

        self.assertEqual(status, 409)
        self.assertIn("email already registered", body["error"]["message"])

    def test_login_and_create_job(self):
        status, login = self.request(
            "POST",
            "/api/auth/login",
            {"email": "demo@example.com", "password": "demo-password"},
        )
        self.assertEqual(status, 200)
        status, me = self.request("GET", "/api/me", token=login["token"])
        self.assertEqual(status, 200)
        project_id = me["projects"][0]["id"]

        status, queues = self.request("GET", f"/api/projects/{project_id}/queues", token=login["token"])
        self.assertEqual(status, 200)
        queue_id = queues["queues"][0]["id"]

        status, body = self.request(
            "POST",
            f"/api/projects/{project_id}/jobs",
            {"queue_id": queue_id, "type": "send_email", "payload": {"to": "customer@example.com"}},
            token=login["token"],
        )

        self.assertEqual(status, 201)
        self.assertEqual(body["job"]["status"], "queued")


if __name__ == "__main__":
    unittest.main()
