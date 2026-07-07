from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
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
        self.assertIn("Resume Registry", body.decode("utf-8"))

    def test_resume_upload_registers_active_resume(self) -> None:
        boundary = "----career-os-test"
        payload = b"unchanged resume bytes"
        body = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="resume"; filename="resume.pdf"\r\n'
            "Content-Type: application/pdf\r\n\r\n"
        ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")

        with run_server() as server:
            status, _headers, response_body = request(
                server,
                "POST",
                "/api/resumes",
                body=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            get_status, _headers, status_body = request(server, "GET", "/api/status")

        response = json.loads(response_body)
        status_response = json.loads(status_body)

        self.assertEqual(201, status)
        self.assertEqual(200, get_status)
        self.assertEqual("resume.pdf", response["resume"]["filename"])
        self.assertEqual(response["resume"]["id"], status_response["active_resume"]["id"])


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


def request(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    *,
    body: bytes | None = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
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
