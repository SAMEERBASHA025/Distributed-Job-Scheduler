from __future__ import annotations

import argparse
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from .db import DEFAULT_DB_PATH, apply_schema, connect
from .scheduler import claim_next_job, finish_execution, heartbeat, register_worker, start_execution, stop_worker

shutdown = threading.Event()


def execute_job(conn, job: dict) -> None:
    execution_id = job["execution_id"]
    start_execution(conn, job["id"], execution_id)
    try:
        payload = job["payload"]
        if payload.get("fail"):
            raise RuntimeError(payload.get("error", "simulated failure"))
        time.sleep(float(payload.get("duration_seconds", 0.25)))
        finish_execution(conn, job["id"], execution_id, True)
    except Exception as exc:
        finish_execution(conn, job["id"], execution_id, False, str(exc))


def run_worker(db_path: str, worker_name: str, concurrency: int, poll_interval: float) -> None:
    conn = connect(db_path)
    apply_schema(conn)
    worker = register_worker(conn, worker_name, concurrency)
    active_lock = threading.Lock()
    active = 0

    def wrapped(job: dict) -> None:
        nonlocal active
        job_conn = connect(db_path)
        try:
            execute_job(job_conn, job)
        finally:
            job_conn.close()
            with active_lock:
                active -= 1

    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        try:
            while not shutdown.is_set():
                with active_lock:
                    heartbeat(conn, worker["id"], active)
                    available = concurrency - active
                for _ in range(max(0, available)):
                    job = claim_next_job(conn, worker["id"])
                    if not job:
                        break
                    with active_lock:
                        active += 1
                    pool.submit(wrapped, job)
                time.sleep(poll_interval)
        finally:
            heartbeat(conn, worker["id"], active, "draining")
            pool.shutdown(wait=True)
            stop_worker(conn, worker["id"])
            conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--worker-name", default="worker-local")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    args = parser.parse_args()

    def handle_signal(signum, frame) -> None:
        shutdown.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    run_worker(args.db, args.worker_name, args.concurrency, args.poll_interval)


if __name__ == "__main__":
    main()
