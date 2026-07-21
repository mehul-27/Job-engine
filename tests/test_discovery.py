from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
import unittest

from career_os.discovery import discover_role
from career_os.domain import RoleTarget


class DiscoveryTests(unittest.TestCase):
    def test_discovers_matching_jobs_from_json_feed(self) -> None:
        with feed_server([
            {"position": "Python Backend Intern", "company": "Acme", "url": "https://example.test/1", "location": "Remote", "description": "Python APIs"},
            {"position": "Sales Associate", "company": "Shop", "url": "https://example.test/2", "location": "Remote"},
        ]) as url:
            role = RoleTarget("rt_1", "Backend Intern", "python, backend", None, "remote", "internship", url, "now", "now")

            jobs = discover_role(role)

        self.assertEqual(1, len(jobs))
        self.assertEqual("Python Backend Intern", jobs[0].title)
        self.assertEqual("Acme", jobs[0].company)


class feed_server:
    def __init__(self, payload: list[dict[str, str]]) -> None:
        self.payload = payload

    def __enter__(self) -> str:
        payload = self.payload

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, format: str, *args: object) -> None:
                return

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        return f"http://{host}:{port}/jobs.json"

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


if __name__ == "__main__":
    unittest.main()
