"""Browser automation for Career OS V1 using Playwright."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

FIELD_PATTERNS: dict[str, list[str]] = {
    "first_name": ["^first name$", "^firstname$", "^given name$", "^fname$"],
    "last_name": ["^last name$", "^lastname$", "^family name$", "^surname$", "^lname$"],
    "email": ["email", "e-mail", "email address", "mail"],
    "phone": ["phone", "telephone", "mobile", "phone number", "contact number", "tel"],
    "linkedin": ["linkedin", "linkedin url", "linkedin profile"],
    "github": ["github", "github url", "github profile"],
    "portfolio": ["portfolio", "website", "personal website", "url"],
    "location": ["location", "city", "address", "current location"],
    "work_authorization": ["work authorization", "work authorization.*us", "visa", "sponsorship", "require.*visa", "legally authorized"],
    "gender": ["gender", "sex"],
    "race": ["race", "ethnicity", "ethnic"],
    "veteran": ["veteran", "military", "disabled veteran"],
    "disability": ["disability", "disabled"],
    "name": ["^name$", "^full name$", "^your name$", "^applicant name$"],
}


def match_field(label: str, field_type: str | None = None) -> str | None:
    text = label.strip().lower()
    for field_id, patterns in FIELD_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text):
                return field_id
    if field_type and field_type in ("email", "tel", "url"):
        type_map = {"email": "email", "tel": "phone", "url": "portfolio"}
        return type_map[field_type]
    return None


class BrowserSession:
    def __init__(self, url: str, user_info: dict[str, str], data_dir: str | Path) -> None:
        self.url = url
        self.user_info = user_info
        self.data_dir = Path(data_dir)
        self._playwright = None
        self._browser = None
        self._page = None
        self.fields_detected: list[dict[str, Any]] = []
        self.fields_filled: list[str] = []
        self.fields_unknown: list[str] = []
        self.screenshots: list[str] = []
        self.is_paused = False
        self.pause_reason: str | None = None

    def start(self) -> None:
        from playwright.sync_api import sync_playwright
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=False)
        self._page = self._browser.new_page()
        self._page.goto(self.url, timeout=30000)

    def detect_fields(self) -> list[dict[str, Any]]:
        if not self._page:
            raise RuntimeError("browser not started")
        fields = self._page.evaluate("""
            () => {
                const inputs = document.querySelectorAll('input, select, textarea');
                return Array.from(inputs).map(el => {
                    const label = el.labels && el.labels[0]
                        ? el.labels[0].textContent.trim()
                        : (el.placeholder || el.name || el.id || '');
                    return {
                        tag: el.tagName.toLowerCase(),
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        label: label,
                        required: el.required || false,
                        visible: el.offsetParent !== null,
                    };
                }).filter(f => f.visible);
            }
        """)
        self.fields_detected = fields
        return fields

    def fill_known_fields(self) -> None:
        if not self._page:
            raise RuntimeError("browser not started")
        self.fields_filled = []
        self.fields_unknown = []
        for field in self.fields_detected:
            label_text = field["label"] or field["placeholder"] or field["name"]
            ftype = field["type"]
            matched = match_field(label_text, ftype)
            selector = f'[name="{field["name"]}"]' if field["name"] else (f'#{field["id"]}' if field["id"] else "")
            if not selector:
                selector = f'input[placeholder="{field["placeholder"]}"]'
            if matched and matched in self.user_info:
                value = self.user_info[matched]
                if value:
                    try:
                        if field["tag"] == "select":
                            self._page.select_option(selector, value)
                        else:
                            self._page.fill(selector, value)
                        self.fields_filled.append(matched)
                    except Exception:
                        self._try_fill_js(selector, value)
                        self.fields_filled.append(matched + "(js)")
                    continue
            if field.get("required"):
                self.fields_unknown.append(label_text)

    def _try_fill_js(self, selector: str, value: str) -> None:
        if not self._page:
            return
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        try:
            self._page.evaluate(f"document.querySelector('{selector}').value = '{escaped}';")
        except Exception:
            pass

    def screenshot(self, name: str = "screenshot") -> str:
        if not self._page:
            raise RuntimeError("browser not started")
        shot_dir = self.data_dir / "screenshots"
        shot_dir.mkdir(parents=True, exist_ok=True)
        path = str(shot_dir / f"{name}_{int(time.time())}.png")
        self._page.screenshot(path=path)
        self.screenshots.append(path)
        return path

    def pause(self, reason: str) -> None:
        self.is_paused = True
        self.pause_reason = reason

    def resume(self) -> None:
        self.is_paused = False
        self.pause_reason = None

    def close(self) -> None:
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._page = None
