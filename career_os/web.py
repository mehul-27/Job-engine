"""Local web GUI for Career OS milestone 3."""

from __future__ import annotations

import argparse
import html
import json
import mimetypes
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from .storage import CareerStore

DEFAULT_DATABASE = Path("career-os-data") / "career-os.sqlite"
DEFAULT_DATA_DIR = Path("career-os-data")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def create_handler(database_path: str | Path, data_dir: str | Path) -> type[BaseHTTPRequestHandler]:
    store = CareerStore(database_path)
    data_root = Path(data_dir)
    store.initialize()

    class CareerOSHandler(BaseHTTPRequestHandler):
        server_version = "CareerOS/0.3"

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                self._send_html(render_index())
                return
            if path == "/api/status":
                self._send_json({"ok": True, "active_resume": serialize_resume(store.get_active_resume())})
                return
            if path == "/api/resumes":
                self._send_json({"resumes": [serialize_resume(resume) for resume in store.list_resumes()]})
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/resumes":
                self._handle_resume_upload()
                return
            if path.startswith("/api/resumes/") and path.endswith("/active"):
                resume_id = path.removeprefix("/api/resumes/").removesuffix("/active")
                try:
                    resume = store.set_active_resume(resume_id)
                except LookupError as error:
                    self._send_json({"error": str(error)}, HTTPStatus.NOT_FOUND)
                    return
                self._send_json({"resume": serialize_resume(resume)})
                return
            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def log_message(self, format: str, *args: object) -> None:
            return

        def _handle_resume_upload(self) -> None:
            content_type = self.headers.get("Content-Type", "")
            content_length = int(self.headers.get("Content-Length", "0") or "0")
            if content_length <= 0:
                self._send_json({"error": "resume file is required"}, HTTPStatus.BAD_REQUEST)
                return
            if content_length > MAX_UPLOAD_BYTES:
                self._send_json({"error": "resume file is too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
                return
            body = self.rfile.read(content_length)
            try:
                filename, payload = extract_resume_upload(content_type, body)
            except ValueError as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return
            resume_dir = data_root / "resumes"
            resume_dir.mkdir(parents=True, exist_ok=True)
            safe_name = safe_filename(filename)
            stored_path = resume_dir / f"{uuid4().hex}_{safe_name}"
            stored_path.write_bytes(payload)
            resume = store.register_resume(stored_path, make_active=True, filename=safe_name)
            self._send_json({"resume": serialize_resume(resume)}, HTTPStatus.CREATED)

        def _send_html(self, content: str) -> None:
            data = content.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _send_json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return CareerOSHandler


def extract_resume_upload(content_type: str, body: bytes) -> tuple[str, bytes]:
    if content_type.startswith("application/x-www-form-urlencoded"):
        form = parse_qs(body.decode("utf-8"))
        path_values = form.get("path", [])
        if not path_values:
            raise ValueError("resume file is required")
        path = Path(path_values[0]).expanduser().resolve()
        if not path.is_file():
            raise ValueError("resume path does not exist")
        return path.name, path.read_bytes()

    boundary_match = re.search(r"boundary=([^;]+)", content_type)
    if not boundary_match:
        raise ValueError("multipart upload is required")
    boundary = boundary_match.group(1).strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    for part in body.split(delimiter):
        if b"Content-Disposition" not in part or b'name="resume"' not in part:
            continue
        header_blob, separator, payload = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        headers = header_blob.decode("utf-8", errors="replace")
        filename_match = re.search(r'filename="([^"]+)"', headers)
        if not filename_match:
            raise ValueError("resume filename is missing")
        payload = payload.rstrip(b"\r\n")
        if payload.endswith(b"--"):
            payload = payload[:-2].rstrip(b"\r\n")
        if not payload:
            raise ValueError("resume file is empty")
        return filename_match.group(1), payload
    raise ValueError("resume file is required")


def safe_filename(filename: str) -> str:
    name = Path(filename).name.strip() or "resume.bin"
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name[:120] or "resume.bin"


def serialize_resume(resume: object | None) -> dict[str, object] | None:
    if resume is None:
        return None
    return {
        "id": resume.id,
        "file_path": resume.file_path,
        "filename": resume.filename,
        "checksum_sha256": resume.checksum_sha256,
        "is_active": resume.is_active,
        "created_at": resume.created_at,
    }


def render_index() -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Career OS</title>
  <style>{CSS}</style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand"><span class="mark">CO</span><span>Career OS</span></div>
      <nav>
        <button class="nav-item active">Resume</button>
        <button class="nav-item" disabled>Roles</button>
        <button class="nav-item" disabled>Opportunities</button>
        <button class="nav-item" disabled>Applications</button>
      </nav>
    </aside>
    <main class="workspace">
      <header class="topbar">
        <div>
          <p class="eyebrow">Milestone 3</p>
          <h1>Resume Registry</h1>
        </div>
        <div id="server-status" class="status-pill">Checking</div>
      </header>
      <section class="resume-layout">
        <div class="panel primary-panel">
          <div class="panel-head">
            <div>
              <p class="eyebrow">Active resume</p>
              <h2 id="active-title">No resume registered</h2>
            </div>
          </div>
          <dl id="active-meta" class="meta-grid"></dl>
          <form id="upload-form" class="upload-box">
            <input id="resume-input" name="resume" type="file" required>
            <button type="submit">Register Resume</button>
          </form>
        </div>
        <aside class="panel inspector">
          <p class="eyebrow">Next action</p>
          <h2>Register unchanged resume file</h2>
          <p>Career OS stores checksum and active default only. It does not parse, rewrite, or tailor resume content.</p>
        </aside>
      </section>
      <section class="panel list-panel">
        <div class="panel-head">
          <h2>Resume history</h2>
        </div>
        <div id="resume-list" class="resume-list"></div>
      </section>
    </main>
  </div>
  <script>{JS}</script>
</body>
</html>"""


CSS = r"""
:root {
  --ink: #17140f;
  --muted: #746c60;
  --paper: #f5f0e6;
  --panel: #fffaf0;
  --line: #d8cdb9;
  --accent: #0d6b5f;
  --accent-dark: #084a42;
  --warn: #a6531b;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  min-height: 100vh;
  color: var(--ink);
  background: linear-gradient(135deg, #f7f2e7 0%, #eee5d4 100%);
  font-family: Georgia, 'Times New Roman', serif;
}
button, input { font: inherit; }
.app-shell { display: grid; grid-template-columns: 240px 1fr; min-height: 100vh; }
.sidebar { border-right: 1px solid var(--line); padding: 24px 18px; background: #191713; color: #f7f0e3; }
.brand { display: flex; align-items: center; gap: 10px; font-weight: 700; letter-spacing: .04em; margin-bottom: 34px; }
.mark { display: grid; place-items: center; width: 38px; height: 38px; border: 1px solid #f7f0e3; color: #f7f0e3; }
nav { display: grid; gap: 8px; }
.nav-item { text-align: left; border: 1px solid #3b3429; background: transparent; color: #c9bfae; padding: 12px 13px; cursor: pointer; }
.nav-item.active { background: #f7f0e3; color: #191713; }
.nav-item:disabled { opacity: .45; cursor: not-allowed; }
.workspace { padding: 28px; }
.topbar { display: flex; justify-content: space-between; align-items: start; margin-bottom: 22px; }
h1, h2, p { margin-top: 0; }
h1 { font-size: 40px; line-height: 1; margin-bottom: 0; }
h2 { font-size: 22px; margin-bottom: 8px; }
.eyebrow { color: var(--accent); text-transform: uppercase; letter-spacing: .14em; font-size: 12px; font-weight: 700; margin-bottom: 6px; }
.status-pill { border: 1px solid var(--line); background: var(--panel); padding: 9px 12px; min-width: 92px; text-align: center; }
.resume-layout { display: grid; grid-template-columns: minmax(0, 1fr) 320px; gap: 18px; align-items: stretch; }
.panel { background: rgba(255,250,240,.88); border: 1px solid var(--line); box-shadow: 0 18px 50px rgba(67, 49, 24, .08); padding: 20px; }
.panel-head { display: flex; justify-content: space-between; gap: 16px; align-items: start; }
.meta-grid { display: grid; grid-template-columns: 130px 1fr; gap: 10px 14px; margin: 20px 0; color: var(--muted); }
.meta-grid dt { color: var(--ink); font-weight: 700; }
.meta-grid dd { margin: 0; word-break: break-all; }
.upload-box { border: 1px dashed var(--accent); padding: 18px; display: grid; gap: 14px; background: #f7f2e8; }
.upload-box button, .small-action { border: 0; background: var(--accent); color: white; padding: 11px 14px; cursor: pointer; }
.upload-box button:hover, .small-action:hover { background: var(--accent-dark); }
.inspector p { color: var(--muted); line-height: 1.5; }
.list-panel { margin-top: 18px; }
.resume-list { display: grid; gap: 10px; }
.resume-row { display: grid; grid-template-columns: 1fr auto; gap: 14px; align-items: center; border-top: 1px solid var(--line); padding: 14px 0 4px; }
.resume-name { font-weight: 700; margin-bottom: 4px; }
.resume-detail { color: var(--muted); font-size: 13px; word-break: break-all; }
.badge { display: inline-block; border: 1px solid var(--accent); color: var(--accent); padding: 3px 8px; font-size: 12px; margin-left: 8px; }
@media (max-width: 860px) {
  .app-shell { grid-template-columns: 1fr; }
  .sidebar { border-right: 0; border-bottom: 1px solid #3b3429; }
  .resume-layout { grid-template-columns: 1fr; }
}
"""


JS = r"""
const statusEl = document.querySelector('#server-status');
const activeTitle = document.querySelector('#active-title');
const activeMeta = document.querySelector('#active-meta');
const listEl = document.querySelector('#resume-list');
const form = document.querySelector('#upload-form');

function shortHash(value) { return value ? value.slice(0, 12) : ''; }

function renderActive(resume) {
  if (!resume) {
    activeTitle.textContent = 'No resume registered';
    activeMeta.innerHTML = '<dt>Status</dt><dd>Upload unchanged resume file to continue.</dd>';
    return;
  }
  activeTitle.textContent = resume.filename;
  activeMeta.innerHTML = `
    <dt>Path</dt><dd>${resume.file_path}</dd>
    <dt>Checksum</dt><dd>${shortHash(resume.checksum_sha256)}</dd>
    <dt>Added</dt><dd>${resume.created_at}</dd>
  `;
}

function renderList(resumes) {
  if (!resumes.length) {
    listEl.innerHTML = '<p class="resume-detail">No resume history yet.</p>';
    return;
  }
  listEl.innerHTML = resumes.map((resume) => `
    <div class="resume-row">
      <div>
        <div class="resume-name">${resume.filename}${resume.is_active ? '<span class="badge">active</span>' : ''}</div>
        <div class="resume-detail">${resume.file_path}</div>
      </div>
      ${resume.is_active ? '' : `<button class="small-action" data-id="${resume.id}">Make active</button>`}
    </div>
  `).join('');
  document.querySelectorAll('[data-id]').forEach((button) => {
    button.addEventListener('click', async () => {
      await fetch(`/api/resumes/${button.dataset.id}/active`, { method: 'POST' });
      await refresh();
    });
  });
}

async function refresh() {
  const [status, resumes] = await Promise.all([
    fetch('/api/status').then((r) => r.json()),
    fetch('/api/resumes').then((r) => r.json()),
  ]);
  statusEl.textContent = status.ok ? 'Ready' : 'Offline';
  renderActive(status.active_resume);
  renderList(resumes.resumes || []);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const data = new FormData(form);
  statusEl.textContent = 'Saving';
  const response = await fetch('/api/resumes', { method: 'POST', body: data });
  if (!response.ok) {
    const payload = await response.json();
    statusEl.textContent = payload.error || 'Failed';
    return;
  }
  form.reset();
  await refresh();
});

refresh().catch(() => { statusEl.textContent = 'Offline'; });
"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the local Career OS GUI")
    parser.add_argument("--db", default=str(DEFAULT_DATABASE), help="Path to SQLite database")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Directory for uploaded local files")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    handler = create_handler(args.db, args.data_dir)
    server = ThreadingHTTPServer((args.host, args.port), handler)
    print(f"Career OS GUI running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
