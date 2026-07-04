import tempfile
import threading
import unittest
from pathlib import Path

from app.db import apply_schema, connect
from app.main import seed
from app.scheduler import claim_next_job, create_job, finish_execution, queue_stats, register_worker, start_execution


class SchedulerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        self.conn = connect(self.db_path)
        apply_schema(self.conn)
        seed(self.conn)
        self.project_id = self.conn.execute("SELECT id FROM projects LIMIT 1").fetchone()["id"]
        self.queue_id = self.conn.execute("SELECT id FROM queues LIMIT 1").fetchone()["id"]

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_atomic_claim_allows_only_one_worker_to_claim_single_job(self):
        self.conn.execute("DELETE FROM jobs")
        create_job(self.conn, self.project_id, self.queue_id, "single", {"duration_seconds": 0})
        workers = [register_worker(self.conn, f"worker-{i}", 1) for i in range(6)]
        claimed = []
        lock = threading.Lock()

        def claim(worker):
            conn = connect(self.db_path)
            try:
                job = claim_next_job(conn, worker["id"])
                if job:
                    with lock:
                        claimed.append(job["id"])
            finally:
                conn.close()

        threads = [threading.Thread(target=claim, args=(worker,)) for worker in workers]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(claimed), 1)
        self.assertEqual(len(set(claimed)), 1)

    def test_failed_job_retries_then_moves_to_dead_letter(self):
        self.conn.execute("DELETE FROM jobs")
        job = create_job(self.conn, self.project_id, self.queue_id, "fails", {"fail": True}, max_attempts=1)
        worker = register_worker(self.conn, "worker-a", 1)
        claimed = claim_next_job(self.conn, worker["id"])
        start_execution(self.conn, claimed["id"], claimed["execution_id"])
        finish_execution(self.conn, claimed["id"], claimed["execution_id"], False, "boom")

        stored = self.conn.execute("SELECT status FROM jobs WHERE id = ?", (job["id"],)).fetchone()
        dlq = self.conn.execute("SELECT reason FROM dead_letter_queue WHERE job_id = ?", (job["id"],)).fetchone()

        self.assertEqual(stored["status"], "dead_letter")
        self.assertEqual(dlq["reason"], "boom")

    def test_queue_stats_counts_lifecycle_states(self):
        stats = queue_stats(self.conn, self.project_id)
        self.assertEqual(stats[0]["queued"], 2)
        self.assertEqual(stats[0]["running"], 0)


if __name__ == "__main__":
    unittest.main()
