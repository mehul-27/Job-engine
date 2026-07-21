"""Local web GUI for Career OS with HTMX + Jinja2."""

from __future__ import annotations

import argparse
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .ai import create_provider
from .browser import BrowserSession
from .discovery import discover_role
from .resume import (
    compile_latex,
    cover_letter_to_latex,
    generate_cover_letter,
    generate_tailored_resume,
    tailored_to_latex,
)
from .storage import CareerStore

DEFAULT_DATABASE = Path("career-os-data") / "career-os.sqlite"
DEFAULT_DATA_DIR = Path("career-os-data")
DEFAULT_SOURCE_URL = "https://remoteok.com/api"
MAX_UPLOAD_BYTES = 20 * 1024 * 1024

_browser_sessions: dict[str, BrowserSession] = {}

_templates = Environment(
    loader=FileSystemLoader(Path(__file__).parent / "templates"),
    autoescape=select_autoescape(),
)


def _render(name: str, **kwargs: Any) -> str:
    return _templates.get_template(name).render(**kwargs)


def _parse_payload(handler: BaseHTTPRequestHandler) -> dict[str, str]:
    length = int(handler.headers.get("Content-Length", "0") or "0")
    body = handler.rfile.read(length)
    ct = handler.headers.get("Content-Type", "")
    if ct.startswith("application/json"):
        payload = json.loads(body.decode("utf-8") or "{}")
        return {str(k): str(v) for k, v in payload.items() if v is not None}
    form = parse_qs(body.decode("utf-8"))
    return {k: v[0] for k, v in form.items() if v}


def serialize_opportunity(opp: object) -> dict[str, object]:
    return dict(
        id=opp.id, role_target_id=opp.role_target_id, title=opp.title,
        company=opp.company, url=opp.url, location=opp.location,
        status=opp.status, source=opp.source, description=opp.description,
        created_at=opp.created_at,
    )


def create_handler(database_path: str | Path, data_dir: str | Path) -> type[BaseHTTPRequestHandler]:
    store = CareerStore(database_path)
    data_root = Path(data_dir)
    store.initialize()

    class CareerOSHandler(BaseHTTPRequestHandler):
        server_version = "CareerOS/0.5"

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            # HTMX fragments
            if path == "/hx/dashboard":
                return self._hx_dashboard()
            if path == "/hx/resume":
                return self._hx_resume()
            if path == "/hx/roles":
                return self._hx_roles()
            if path == "/hx/opportunities":
                return self._hx_opportunities(params)
            if path == "/hx/companies":
                return self._hx_companies()
            if path == "/hx/workspaces":
                return self._hx_workspaces()
            if path.startswith("/hx/workspace/"):
                ws_id = path.removeprefix("/hx/workspace/")
                return self._hx_workspace_detail(ws_id)

            # File serving
            if path.startswith("/files/"):
                return self._serve_file(path.removeprefix("/files/"))

            # JSON API
            if path == "/api/status":
                return self._json({"ok": True, "active_resume": _serialize_resume(store.get_active_resume())})
            if path == "/api/resumes":
                return self._json({"resumes": [_serialize_resume(r) for r in store.list_resumes()]})
            if path == "/api/roles":
                return self._json({"roles": [_serialize_role(r) for r in store.list_role_targets()]})
            if path == "/api/opportunities":
                return self._json({"opportunities": [serialize_opportunity(o) for o in store.list_opportunities()]})
            if path == "/api/companies":
                return self._json({"companies": [_serialize_company(c) for c in store.list_companies()]})

            if path == "/":
                return self._html(_render("index.html"))

            self.send_error(HTTPStatus.NOT_FOUND, "Not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/api/resumes":
                return self._handle_resume_upload()
            if path == "/api/roles":
                return self._handle_role_create()
            if path == "/api/companies":
                return self._handle_company_upsert()

            if path.startswith("/api/resumes/") and path.endswith("/active"):
                resume_id = path.removeprefix("/api/resumes/").removesuffix("/active")
                try:
                    r = store.set_active_resume(resume_id)
                except LookupError as e:
                    return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
                return self._json({"resume": _serialize_resume(r)})

            if path.startswith("/api/roles/") and path.endswith("/discover"):
                role_id = path.removeprefix("/api/roles/").removesuffix("/discover")
                return self._handle_discover(role_id)

            if path.startswith("/api/opportunities/") and path.endswith("/tailor"):
                opp_id = path.removeprefix("/api/opportunities/").removesuffix("/tailor")
                return self._handle_tailor(opp_id)

            if path.startswith("/api/opportunities/") and path.endswith("/status"):
                opp_id = path.removeprefix("/api/opportunities/").removesuffix("/status")
                return self._handle_opportunity_status(opp_id)

            if path.startswith("/api/tailored/") and path.endswith("/approve"):
                resume_id = path.removeprefix("/api/tailored/").removesuffix("/approve")
                return self._handle_approve_tailored(resume_id)

            if path.startswith("/api/opportunities/") and path.endswith("/apply"):
                opp_id = path.removeprefix("/api/opportunities/").removesuffix("/apply")
                return self._handle_apply(opp_id)

            if path.startswith("/api/workspace/") and path.endswith("/advance"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/advance")
                return self._handle_workspace_advance(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/cover-letter"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/cover-letter")
                return self._handle_cover_letter(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/browser-start"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/browser-start")
                return self._handle_browser_start(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/browser-fill"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/browser-fill")
                return self._handle_browser_fill(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/browser-pause"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/browser-pause")
                return self._handle_browser_pause(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/browser-resume"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/browser-resume")
                return self._handle_browser_resume(ws_id)

            if path.startswith("/api/workspace/") and path.endswith("/browser-close"):
                ws_id = path.removeprefix("/api/workspace/").removesuffix("/browser-close")
                return self._handle_browser_close(ws_id)

        def _hx_dashboard(self) -> None:
            active = store.get_active_resume()
            opps = store.list_opportunities()
            recent = opps[:10]
            stats = {"new": 0, "saved": 0, "skipped": 0, "applying": 0, "blacklisted": 0}
            for o in opps:
                s = o.status
                if s in stats:
                    stats[s] += 1
            workspaces = []
            for ws in store.list_workspaces():
                if ws.status not in ("submitted", "abandoned"):
                    try:
                        opp = store.get_opportunity(ws.opportunity_id)
                        workspaces.append(dict(id=ws.id, status=ws.status, title=opp.title, company=opp.company))
                    except LookupError:
                        pass
            self._html(_render("partials/dashboard.html",
                active_resume=active,
                recent_opportunities=recent,
                opportunity_count=len(opps),
                stats=stats,
                workspaces=workspaces,
            ))

        def _hx_resume(self) -> None:
            self._html(_render("partials/resume.html",
                active_resume=store.get_active_resume(),
                resumes=store.list_resumes(),
            ))

        def _hx_roles(self) -> None:
            self._html(_render("partials/roles.html",
                roles=store.list_role_targets(),
            ))

        def _hx_opportunities(self, params: dict[str, list[str]]) -> None:
            opps = store.list_opportunities()
            status_filter = params.get("status", [None])[0]
            if status_filter and status_filter != "all":
                opps = [o for o in opps if o.status == status_filter]
            self._html(_render("partials/opportunities.html", opportunities=opps))

        def _hx_companies(self) -> None:
            self._html(_render("partials/companies.html",
                companies=store.list_companies(),
            ))

        def _hx_workspaces(self) -> None:
            workspaces = store.list_workspaces()
            enriched = []
            for ws in workspaces:
                try:
                    opp = store.get_opportunity(ws.opportunity_id)
                    enriched.append(dict(id=ws.id, status=ws.status, created_at=ws.created_at, opportunity_title=opp.title, opportunity_company=opp.company))
                except LookupError:
                    enriched.append(dict(id=ws.id, status=ws.status, created_at=ws.created_at, opportunity_title="Unknown", opportunity_company=""))
            self._html(_render("partials/workspaces.html", workspaces=enriched))

        def _hx_workspace_detail(self, ws_id: str) -> None:
            try:
                ws = store.get_workspace(ws_id)
                opp = store.get_opportunity(ws.opportunity_id)
                materials = store.list_materials(ws_id)
                approvals = store.list_approvals(ws_id)
            except LookupError as e:
                return self._html(f'<p class="empty">{e}</p>', HTTPStatus.NOT_FOUND)
            self._html(_render("partials/workspace_detail.html",
                ws=ws, opp=opp, materials=materials, approvals=approvals,
            ))

        def _handle_resume_upload(self) -> None:
            ct = self.headers.get("Content-Type", "")
            cl = int(self.headers.get("Content-Length", "0") or "0")
            if cl <= 0:
                return self._json({"error": "resume file required"}, HTTPStatus.BAD_REQUEST)
            if cl > MAX_UPLOAD_BYTES:
                return self._json({"error": "resume too large"}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            body = self.rfile.read(cl)
            try:
                filename, payload = _extract_upload(ct, body)
            except ValueError as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            resume_dir = data_root / "resumes"
            resume_dir.mkdir(parents=True, exist_ok=True)
            safe = _safe_name(filename)
            stored = resume_dir / f"{uuid4().hex}_{safe}"
            stored.write_bytes(payload)
            record = store.register_resume(stored, make_active=True, filename=safe)
            return self._json({"resume": _serialize_resume(record)}, HTTPStatus.CREATED)

        def _handle_role_create(self) -> None:
            data = _parse_payload(self)
            try:
                role = store.add_role_target(
                    title=data.get("title", ""),
                    keywords=data.get("keywords", ""),
                    location=data.get("location") or None,
                    remote_preference=data.get("remote_preference", "any") or "any",
                    job_type=data.get("job_type") or None,
                    source_url=data.get("source_url") or DEFAULT_SOURCE_URL,
                )
            except ValueError as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            return self._json({"role": _serialize_role(role)}, HTTPStatus.CREATED)

        def _handle_discover(self, role_id: str) -> None:
            try:
                role = store.get_role_target(role_id)
                discovered = discover_role(role)
                saved = store.save_discovered_opportunities(role.id, discovered)
                for opp in saved:
                    store.upsert_company(name=opp.company, url=opp.url)
            except LookupError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
            except Exception as e:
                return self._json({"error": f"discovery failed: {e}"}, HTTPStatus.BAD_GATEWAY)
            return self._json({"count": len(saved), "opportunities": [serialize_opportunity(j) for j in saved]})

        def _handle_tailor(self, opp_id: str) -> None:
            try:
                opp = store.get_opportunity(opp_id)
            except LookupError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
            try:
                ai = create_provider()
            except RuntimeError as e:
                return self._json({"error": str(e)}, HTTPStatus.SERVICE_UNAVAILABLE)

            active = store.get_active_resume()
            if not active:
                return self._json({"error": "no active resume"}, HTTPStatus.BAD_REQUEST)
            resume_path = Path(active.file_path)
            if not resume_path.exists():
                return self._json({"error": "resume file not found"}, HTTPStatus.BAD_REQUEST)

            kb = store.list_knowledge_items()
            kb_list = [{"kind": k.kind, "title": k.title, "body": k.body} for k in kb]

            try:
                result = generate_tailored_resume(
                    job_title=opp.title,
                    job_description=opp.description,
                    master_resume_path=resume_path,
                    knowledge_items=kb_list,
                    ai_provider=ai,
                )
            except Exception as e:
                return self._json({"error": f"tailoring failed: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

            tailor_dir = data_root / "tailored"
            tailor_dir.mkdir(parents=True, exist_ok=True)
            stem = f"tailored_{opp_id[:8]}"
            tex_content = tailored_to_latex(
                result,
                name=opp.company,
                contact=["email@example.com"],
            )
            tex_path = tailor_dir / f"{stem}.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            pdf_path = compile_latex(tex_content, tailor_dir, stem=stem)

            existing = store.list_tailored_resumes(opp_id)
            version = (existing[0].version + 1) if existing else 1

            provenance = json.dumps(result.get("_provenance", {}), indent=2)
            saved_path = str(pdf_path) if pdf_path else str(tex_path)
            tr = store.save_tailored_resume(
                opportunity_id=opp_id,
                file_path=saved_path,
                provenance=provenance,
                version=version,
            )

            self._html(_render("partials/tailored_result.html",
                version=version,
                pdf_path=str(pdf_path.relative_to(data_root)) if pdf_path else None,
                tex_path=str(tex_path.relative_to(data_root)),
                is_approved=False,
                resume_id=tr.id,
                provenance=provenance,
            ))

        def _handle_opportunity_status(self, opp_id: str) -> None:
            data = _parse_payload(self)
            status = data.get("status", "")
            try:
                updated = store.update_opportunity_status(opp_id, status)
                if status == "blacklisted":
                    store.upsert_company(name=updated.company, is_blacklisted=True)
            except (ValueError, LookupError) as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            self._html(_render("partials/opportunity_row.html", opp=updated))

        def _handle_company_upsert(self) -> None:
            data = _parse_payload(self)
            name = data.get("name", "")
            if not name:
                return self._json({"error": "name required"}, HTTPStatus.BAD_REQUEST)
            company = store.upsert_company(
                name=name,
                url=data.get("url") or None,
                notes=data.get("notes") or None,
                is_blacklisted=bool(data.get("is_blacklisted")),
            )
            self._html(_render("partials/company_row.html", c=company), HTTPStatus.CREATED)

        def _handle_approve_tailored(self, resume_id: str) -> None:
            try:
                tr = store.approve_tailored_resume(resume_id)
            except LookupError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
            self._html(_render("partials/tailored_result.html",
                version=tr.version,
                pdf_path=None,
                tex_path=tr.file_path,
                is_approved=True,
                resume_id=tr.id,
                provenance=tr.provenance,
            ))

        def _handle_apply(self, opp_id: str) -> None:
            existing = store.get_workspace_by_opportunity(opp_id)
            if existing:
                ws_id = existing.id
            else:
                ws = store.create_workspace(opp_id)
                ws_id = ws.id
            self._html(
                '<div class="panel" style="margin-top:8px;border-left:3px solid var(--accent);">'
                f'<p class="eyebrow">Workspace created</p>'
                f'<a href="/workspace/{ws_id}" class="btn btn-sm" hx-get="/hx/workspace/{ws_id}" hx-target="#workspace" hx-push-url="true">Open Workspace</a>'
                '</div>'
            )

        def _handle_workspace_advance(self, ws_id: str) -> None:
            data = _parse_payload(self)
            next_status = data.get("status", "")
            try:
                ws = store.update_workspace_status(ws_id, next_status)
                opp = store.get_opportunity(ws.opportunity_id)
                materials = store.list_materials(ws_id)
                approvals = store.list_approvals(ws_id)
                store.add_approval(workspace_id=ws_id, action=f"advance_to_{next_status}", is_approved=True)
            except (ValueError, LookupError) as e:
                return self._json({"error": str(e)}, HTTPStatus.BAD_REQUEST)
            self._html(_render("partials/workspace_detail.html",
                ws=ws, opp=opp, materials=materials, approvals=approvals,
            ))

        def _handle_cover_letter(self, ws_id: str) -> None:
            try:
                ws = store.get_workspace(ws_id)
                opp = store.get_opportunity(ws.opportunity_id)
            except LookupError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)
            try:
                ai = create_provider()
            except RuntimeError as e:
                return self._json({"error": str(e)}, HTTPStatus.SERVICE_UNAVAILABLE)

            profile = store.get_active_resume()
            profile_text = f"Resume: {profile.file_path if profile else 'None'}"
            tailored_resumes = store.list_tailored_resumes(opp.id)
            tailored_text = "No tailored resume yet"
            if tailored_resumes:
                tr_path = Path(tailored_resumes[0].file_path)
                if tr_path.exists():
                    try:
                        tailored_text = tr_path.read_text(encoding="utf-8")
                    except Exception:
                        tailored_text = "Tailored resume exists but unreadable"
            try:
                body = generate_cover_letter(
                    job_title=opp.title, company=opp.company, job_description=opp.description,
                    tailored_resume_text=tailored_text, user_profile_text=profile_text, ai_provider=ai,
                )
            except Exception as e:
                return self._json({"error": f"cover letter failed: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)

            cl_dir = data_root / "cover_letters"
            cl_dir.mkdir(parents=True, exist_ok=True)
            stem = f"cl_{ws_id[:8]}"
            tex_content = cover_letter_to_latex(body, company=opp.company, job_title=opp.title)
            tex_path = cl_dir / f"{stem}.tex"
            tex_path.write_text(tex_content, encoding="utf-8")
            pdf_path = compile_latex(tex_content, cl_dir, stem=stem)
            store.add_material(workspace_id=ws_id, kind="cover_letter", file_path=str(tex_path))

            pdf_link = f'<a href="/files/{pdf_path.relative_to(data_root)}" class="btn btn-sm" download>Download PDF</a>' if pdf_path else ''
            self._html(
                '<div class="panel" style="margin-top:8px;border-left:3px solid var(--accent);">'
                '<p class="eyebrow">Cover Letter Generated</p>'
                f'<div class="flex">{pdf_link}'
                f'<a href="/files/{tex_path.relative_to(data_root)}" class="btn btn-sm btn-outline" download>Download .tex</a>'
                '</div></div>'
            )

        def _get_browser_user_info(self, opp: object) -> dict[str, str]:
            info: dict[str, str] = {}
            profile = store.get_active_resume()
            if profile:
                stem = Path(profile.file_path).stem
                info["name"] = stem.replace("_", " ").replace("-", " ").title()
            from .domain import Opportunity
            if hasattr(opp, "company") and opp.company:
                info["company"] = opp.company
            try:
                learned = store.get_learned_user_info()
                for k, v in learned.items():
                    info.setdefault(k, v)
            except Exception:
                pass
            return info

        def _browser_status_html(self, ws_id: str) -> str:
            session = _browser_sessions.get(ws_id)
            if session is None:
                return '<p class="empty">Browser not started.</p>'
            status = "paused" if session.is_paused else "active"
            unknown = ""
            if session.fields_unknown:
                unknown = '<p class="empty">Unknown fields: ' + ", ".join(session.fields_unknown) + "</p>"
            screenshots = ""
            if session.screenshots:
                screenshots = f'<p class="detail">{len(session.screenshots)} screenshots captured</p>'
            return (
                f'<div class="panel" style="margin-top:8px;border-left:3px solid var(--accent);">'
                f'<p class="eyebrow">Browser {status}</p>'
                f'<p>{len(session.fields_filled)} fields filled</p>'
                f'{unknown}{screenshots}'
                f'<div class="flex" style="margin-top:8px">'
                + (f'<button class="btn btn-sm" hx-post="/api/workspace/{ws_id}/browser-fill" hx-target="#browser-status" hx-swap="innerHTML">Fill Fields</button>' if not session.is_paused else '')
                + (f'<button class="btn btn-sm btn-outline" hx-post="/api/workspace/{ws_id}/browser-pause" hx-target="#browser-status" hx-swap="innerHTML">Pause</button>' if not session.is_paused else '')
                + (f'<button class="btn btn-sm" hx-post="/api/workspace/{ws_id}/browser-resume" hx-target="#browser-status" hx-swap="innerHTML">Resume</button>' if session.is_paused else '')
                + f'<button class="btn btn-sm btn-danger" hx-post="/api/workspace/{ws_id}/browser-close" hx-target="#browser-status" hx-swap="innerHTML">Close Browser</button>'
                f'</div></div>'
            )

        def _learn_from_session(self, session: BrowserSession) -> None:
            for matched in session.fields_filled:
                val = session.user_info.get(matched, "")
                if val:
                    try:
                        store.upsert_learning_record(matched, val)
                    except Exception:
                        pass

        def _handle_browser_start(self, ws_id: str) -> None:
            try:
                ws = store.get_workspace(ws_id)
                opp = store.get_opportunity(ws.opportunity_id)
            except LookupError as e:
                return self._json({"error": str(e)}, HTTPStatus.NOT_FOUND)

            if ws_id in _browser_sessions:
                return self._html(self._browser_status_html(ws_id))

            ui = self._get_browser_user_info(opp)
            session = BrowserSession(opp.url, ui, data_root)
            try:
                session.start()
            except Exception as e:
                return self._json({"error": f"browser start failed: {e}"}, HTTPStatus.INTERNAL_SERVER_ERROR)
            _browser_sessions[ws_id] = session
            session.detect_fields()
            session.fill_known_fields()
            self._learn_from_session(session)
            session.screenshot("first_load")
            store.add_material(workspace_id=ws_id, kind="screenshot", file_path=session.screenshots[-1])
            self._html(self._browser_status_html(ws_id))

        def _handle_browser_fill(self, ws_id: str) -> None:
            session = _browser_sessions.get(ws_id)
            if not session:
                return self._json({"error": "browser not started"}, HTTPStatus.BAD_REQUEST)
            session.detect_fields()
            session.fill_known_fields()
            self._learn_from_session(session)
            session.screenshot("after_fill")
            store.add_material(workspace_id=ws_id, kind="screenshot", file_path=session.screenshots[-1])
            self._html(self._browser_status_html(ws_id))

        def _handle_browser_pause(self, ws_id: str) -> None:
            session = _browser_sessions.get(ws_id)
            if not session:
                return self._json({"error": "browser not started"}, HTTPStatus.BAD_REQUEST)
            session.pause("user requested pause")
            self._html(self._browser_status_html(ws_id))

        def _handle_browser_resume(self, ws_id: str) -> None:
            session = _browser_sessions.get(ws_id)
            if not session:
                return self._json({"error": "browser not started"}, HTTPStatus.BAD_REQUEST)
            session.resume()
            self._html(self._browser_status_html(ws_id))

        def _handle_browser_close(self, ws_id: str) -> None:
            session = _browser_sessions.pop(ws_id, None)
            if session:
                session.close()
            self._html('<p class="empty">Browser closed.</p>')

        def _serve_file(self, rel_path: str) -> None:
            full = (data_root / rel_path).resolve()
            if not full.is_file():
                return self.send_error(HTTPStatus.NOT_FOUND)
            payload = full.read_bytes()
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Content-Disposition", f'attachment; filename="{full.name}"')
            self.end_headers()
            self.wfile.write(payload)

        def _html(self, content: str, status: HTTPStatus = HTTPStatus.OK) -> None:
            data = content.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _json(self, payload: dict[str, object], status: HTTPStatus = HTTPStatus.OK) -> None:
            data = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, format: str, *args: object) -> None:
            return

    return CareerOSHandler


def _serialize_resume(r: object | None) -> dict[str, object] | None:
    if r is None:
        return None
    return dict(id=r.id, file_path=r.file_path, filename=r.filename,
                checksum_sha256=r.checksum_sha256, is_active=r.is_active,
                created_at=r.created_at)


def _serialize_role(r: object) -> dict[str, object]:
    return dict(id=r.id, title=r.title, keywords=r.keywords, location=r.location,
                remote_preference=r.remote_preference, job_type=r.job_type,
                source_url=r.source_url, created_at=r.created_at)


def _serialize_company(c: object) -> dict[str, object]:
    return dict(id=c.id, name=c.name, url=c.url, notes=c.notes,
                is_blacklisted=c.is_blacklisted, created_at=c.created_at)


def _extract_upload(content_type: str, body: bytes) -> tuple[str, bytes]:
    boundary_match = re.search(r"boundary=([^;]+)", content_type)
    if not boundary_match:
        raise ValueError("multipart upload required")
    boundary = boundary_match.group(1).strip().strip('"').encode("utf-8")
    delimiter = b"--" + boundary
    for part in body.split(delimiter):
        if b"Content-Disposition" not in part or b'name="resume"' not in part:
            continue
        header_blob, sep, payload = part.partition(b"\r\n\r\n")
        if not sep:
            continue
        headers = header_blob.decode("utf-8", errors="replace")
        fm = re.search(r'filename="([^"]+)"', headers)
        if not fm:
            raise ValueError("filename missing in upload")
        payload = payload.rstrip(b"\r\n")
        if payload.endswith(b"--"):
            payload = payload[:-2].rstrip(b"\r\n")
        if not payload:
            raise ValueError("empty file")
        return fm.group(1), payload
    raise ValueError("resume file field not found")


def _safe_name(filename: str) -> str:
    name = Path(filename).name.strip() or "resume.bin"
    name = re.sub(r"[^A-Za-z0-9._ -]", "_", name)
    return name[:120] or "resume.bin"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Career OS GUI")
    parser.add_argument("--db", default=str(DEFAULT_DATABASE))
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    server = ThreadingHTTPServer((args.host, args.port), create_handler(args.db, args.data_dir))
    print(f"Career OS at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
