from __future__ import annotations

import json
import re
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest

from career_os.web import create_handler


class WebServerTests(unittest.TestCase):
    def test_home_page_loads(self) -> None:
        with run_server() as server:
            status, _headers, body = request(server, "GET", "/")

        self.assertEqual(200, status)
        html = body.decode("utf-8")
        self.assertIn("Career OS", html)
        self.assertIn("Dashboard", html)
        self.assertIn("Resume", html)
        self.assertIn("htmx.org", html)

    def test_dashboard_fragment(self) -> None:
        with run_server() as server:
            status, _headers, body = request(server, "GET", "/hx/dashboard")

        self.assertEqual(200, status)
        html = body.decode("utf-8")
        self.assertIn("Active Resume", html)
        self.assertIn("Quick Stats", html)

    def test_resume_upload_registers_active_resume(self) -> None:
        boundary = "----career-os-test"
        payload = b"unchanged resume bytes"
        body = multipart(boundary, "resume", "resume.pdf", payload)

        with run_server() as server:
            status, _headers, response_body = request(server, "POST", "/api/resumes", body=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
            get_status, _headers, status_body = request(server, "GET", "/api/status")

        response = json.loads(response_body)
        status_response = json.loads(status_body)

        self.assertEqual(201, status)
        self.assertEqual(200, get_status)
        self.assertEqual("resume.pdf", response["resume"]["filename"])
        self.assertEqual(response["resume"]["id"], status_response["active_resume"]["id"])

    def test_role_create_and_discover(self) -> None:
        with feed_server([
            {"position": "Python Backend Intern", "company": "Acme", "url": "https://example.test/1", "location": "Remote", "description": "Python APIs"},
            {"position": "Sales Associate", "company": "Shop", "url": "https://example.test/2", "location": "Remote"},
        ]) as feed_url:
            with run_server() as server:
                role_body = json.dumps({"title": "Backend", "keywords": "python", "remote_preference": "remote", "source_url": feed_url}).encode("utf-8")
                status, _headers, role_response = request(server, "POST", "/api/roles", body=role_body, headers={"Content-Type": "application/json"})
                role_id = json.loads(role_response)["role"]["id"]
                discover_status, _headers, discover_response = request(server, "POST", f"/api/roles/{role_id}/discover")
                list_status, _headers, list_response = request(server, "GET", "/api/opportunities")

        self.assertEqual(201, status)
        self.assertEqual(200, discover_status)
        self.assertEqual(200, list_status)
        self.assertEqual(1, json.loads(discover_response)["count"])
        self.assertEqual("Python Backend Intern", json.loads(list_response)["opportunities"][0]["title"])

    def test_company_upsert(self) -> None:
        with run_server() as server:
            body = json.dumps({"name": "TestCorp", "url": "https://test.corp"}).encode("utf-8")
            status, _headers, _resp = request(server, "POST", "/api/companies", body=body, headers={"Content-Type": "application/json"})
            get_status, _headers, get_resp = request(server, "GET", "/api/companies")

        self.assertEqual(201, status)
        self.assertEqual(200, get_status)
        companies = json.loads(get_resp)["companies"]
        self.assertEqual(1, len(companies))
        self.assertEqual("TestCorp", companies[0]["name"])

    def test_opportunity_status_update(self) -> None:
        with feed_server([
            {"position": "Python Dev", "company": "Acme", "url": "https://ex.test/1", "location": "Remote", "description": "Python"},
        ]) as feed_url:
            with run_server() as server:
                role_body = json.dumps({"title": "Dev", "keywords": "python", "remote_preference": "any", "source_url": feed_url}).encode("utf-8")
                _, _, role_resp = request(server, "POST", "/api/roles", body=role_body, headers={"Content-Type": "application/json"})
                role_id = json.loads(role_resp)["role"]["id"]
                request(server, "POST", f"/api/roles/{role_id}/discover")
                list_status, _, list_resp = request(server, "GET", "/api/opportunities")
                opp_id = json.loads(list_resp)["opportunities"][0]["id"]

                status_body = json.dumps({"status": "saved"}).encode("utf-8")
                up_status, _, up_resp = request(server, "POST", f"/api/opportunities/{opp_id}/status", body=status_body, headers={"Content-Type": "application/json"})

                check_status, _, check_resp = request(server, "GET", "/api/opportunities")
                updated = json.loads(check_resp)["opportunities"][0]

        self.assertEqual(200, up_status)
        self.assertEqual("saved", updated["status"])

    def test_apply_creates_workspace(self) -> None:
        with feed_server([
            {"position": "Python Dev", "company": "Acme", "url": "https://ex.test/1", "description": "Python work"},
        ]) as feed_url:
            with run_server() as server:
                role_body = json.dumps({"title": "Dev", "keywords": "python", "remote_preference": "any", "source_url": feed_url}).encode("utf-8")
                _, _, role_resp = request(server, "POST", "/api/roles", body=role_body, headers={"Content-Type": "application/json"})
                role_id = json.loads(role_resp)["role"]["id"]
                request(server, "POST", f"/api/roles/{role_id}/discover")
                list_status, _, list_resp = request(server, "GET", "/api/opportunities")
                opp_id = json.loads(list_resp)["opportunities"][0]["id"]

                apply_status, _, apply_resp = request(server, "POST", f"/api/opportunities/{opp_id}/apply")

                ws_status, _, ws_resp = request(server, "GET", "/hx/workspaces")

        self.assertEqual(200, apply_status)
        self.assertIn("Workspace", apply_resp.decode("utf-8"))
        self.assertEqual(200, ws_status)
        self.assertIn("Acme", ws_resp.decode("utf-8"))

    def test_workspace_advance(self) -> None:
        with feed_server([
            {"position": "Python Dev", "company": "Acme", "url": "https://ex.test/1"},
        ]) as feed_url:
            with run_server() as server:
                role_body = json.dumps({"title": "Dev", "keywords": "python", "remote_preference": "any", "source_url": feed_url}).encode("utf-8")
                _, _, role_resp = request(server, "POST", "/api/roles", body=role_body, headers={"Content-Type": "application/json"})
                role_id = json.loads(role_resp)["role"]["id"]
                request(server, "POST", f"/api/roles/{role_id}/discover")
                _, _, list_resp = request(server, "GET", "/api/opportunities")
                opp_id = json.loads(list_resp)["opportunities"][0]["id"]

                request(server, "POST", f"/api/opportunities/{opp_id}/apply")
                _, _, ws_resp = request(server, "GET", "/hx/workspaces")
                detail_html = ws_resp.decode("utf-8")
                import re
                match = re.search(r'/hx/workspace/([a-z0-9_]+)', detail_html)
                ws_id = match.group(1)

                adv_status, _, adv_resp = request(server, "POST", f"/api/workspace/{ws_id}/advance", body=json.dumps({"status": "preparing"}).encode("utf-8"), headers={"Content-Type": "application/json"})

        self.assertEqual(200, adv_status)
        self.assertIn("preparing", adv_resp.decode("utf-8"))


class run_server:
    def __enter__(self) -> ThreadingHTTPServer:
        self.temp_dir = TemporaryDirectory()
        root = Path(self.temp_dir.name)
        handler = create_handler(root / "career-os.sqlite", root)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temp_dir.cleanup()


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


def multipart(boundary: str, field: str, filename: str, payload: bytes) -> bytes:
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
        "Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")


def request(server: ThreadingHTTPServer, method: str, path: str, *, body: bytes | None = None, headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
    host, port = server.server_address
    connection = HTTPConnection(host, port, timeout=5)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    data = response.read()
    response_headers = {key: value for key, value in response.getheaders()}
    connection.close()
    return response.status, response_headers, data


if __name__ == "__main__":
    unittest.main()
