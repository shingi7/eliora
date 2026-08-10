#!/usr/bin/env python3
"""Dependency-free structural checks for marketing pages and public lab routes."""

from __future__ import annotations

import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARKETING = ["index.html", "services.html", "work.html", "about.html", "contact.html"]
LAB = [
    "reporting-control-room.html",
    "revenue-margin-forecast.html",
    "pipeline-intelligence.html",
    "support-operations.html",
    "executive-demo.html",
    "player-st.html",
    "team-prototype.html",
]
BUSINESS = set(LAB[:4])
LEGACY = ("#1f0a3d", "#2b0a57", "#4b1e8a", "#6a2fbf", "#c7a8f2", "#d1a20f", "ORL_COLORS", "--purple-", "--lavender-", "--gold-")
PRIVATE_ARTIFACT_NAMES = ("outreach.sqlite", "outreach.sqlite3", "token.json", "credentials.json", "client_secret", "api_key", "gmail-token")


class Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.links: list[str] = []
        self.images: list[dict[str, str]] = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        self.tags.append((tag, values))
        if tag == "a":
            self.links.append(values.get("href", ""))
        if tag == "img":
            self.images.append(values)
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title += data


def local_target(value: str, source: Path) -> Path | None:
    if not value or value.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    return (source.parent / parsed.path).resolve()


def check_page(path: Path, lab: bool = False) -> list[str]:
    html = path.read_text(encoding="utf-8")
    lower = html.lower()
    parser = Parser()
    parser.feed(html)
    errors: list[str] = []
    tags = [tag for tag, _ in parser.tags]
    if not parser.title.strip():
        errors.append(f"{path}: missing title")
    if not re.search(r'<meta[^>]+name=["\']description["\']', html, re.I):
        errors.append(f"{path}: missing description")
    if not re.search(r'<link[^>]+rel=["\']canonical["\']', html, re.I):
        errors.append(f"{path}: missing canonical")
    if len(re.findall(r"<h1\b", html, re.I)) != 1:
        errors.append(f"{path}: expected exactly one h1")
    for landmark in ("header", "main", "footer"):
        if landmark not in tags:
            errors.append(f"{path}: missing {landmark} landmark")
    if "skip-link" not in lower and "lab-skip" not in lower:
        errors.append(f"{path}: missing skip link")
    for image in parser.images:
        if "alt" not in image:
            errors.append(f"{path}: image missing alt ({image.get('src', 'unknown')})")
        target = local_target(image.get("src", ""), path)
        if target and not target.exists():
            errors.append(f"{path}: missing image target {image.get('src')}")
    for href in parser.links:
        if not href or href in ("#", "#0"):
            errors.append(f"{path}: empty/placeholder link")
        target = local_target(href, path)
        if target and not target.exists():
            errors.append(f"{path}: missing link target {href}")
        if lab and (href.startswith("/site/") or href.startswith("/site")):
            errors.append(f"{path}: root-relative lab link {href}")
    for tag, attrs in parser.tags:
        resource = attrs.get("src", "") or attrs.get("href", "")
        if resource.lower().split("?")[0].endswith((".js", ".mjs", ".css")):
            target = local_target(resource, path)
            if target and not target.exists():
                errors.append(f"{path}: missing resource {resource}")
    if any(token in lower for token in ("lorem ipsum", "example.com", "your-email", 'href="#"')):
        errors.append(f"{path}: placeholder content or URL")
    if lab and "back to work" not in lower:
        errors.append(f"{path}: missing Back to Work")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in DOCS.rglob("*"):
        if path.is_file() and any(token in path.name.lower() for token in PRIVATE_ARTIFACT_NAMES):
            errors.append(f"public docs contains private outreach artifact name: {path}")
    cname = DOCS / "CNAME"
    if not cname.exists() or cname.read_text(encoding="utf-8").strip() != "elioratechsolutions.com":
        errors.append("docs/CNAME is missing or incorrect")
    for page in MARKETING:
        path = DOCS / page
        if path.exists():
            errors.extend(check_page(path))
        else:
            errors.append(f"missing generated marketing page: {path}")
    for page in LAB:
        path = DOCS / "site" / page
        if path.exists():
            errors.extend(check_page(path, lab=True))
        else:
            errors.append(f"missing generated lab page: {path}")
    work = (DOCS / "work.html").read_text(encoding="utf-8") if (DOCS / "work.html").exists() else ""
    for page in LAB:
        if f"site/{page}" not in work:
            errors.append(f"work.html missing lab link site/{page}")
    for page in BUSINESS:
        content = (DOCS / "site" / page).read_text(encoding="utf-8")
        if "synthetic" not in content.lower():
            errors.append(f"{page}: missing synthetic disclosure")
    lab_files = [DOCS / "site" / page for page in LAB] + [DOCS / "site" / "lab-shell.css", DOCS / "site" / "lab-shell.js"]
    for path in lab_files:
        if not path.exists():
            errors.append(f"missing lab resource: {path}")
            continue
        content = path.read_text(encoding="utf-8").lower()
        for token in LEGACY:
            if token.lower() in content:
                errors.append(f"{path}: legacy palette token {token}")
    for page in BUSINESS:
        content = (DOCS / "site" / page).read_text(encoding="utf-8").lower()
        if "plotly" in content or "cdn." in content:
            errors.append(f"{page}: new business demo must not load external chart libraries")
    for page in ("player-st.html", "team-prototype.html"):
        content = (DOCS / "site" / page).read_text(encoding="utf-8").lower()
        if "plotly" not in content:
            errors.append(f"{page}: expected preserved Plotly dependency")
    sitemap = (ROOT / "sitemap.xml").read_text(encoding="utf-8") if (ROOT / "sitemap.xml").exists() else ""
    for page in MARKETING + [f"site/{item}" for item in LAB]:
        if f"https://elioratechsolutions.com/{page}" not in sitemap and page != "index.html":
            errors.append(f"sitemap missing {page}")
    for resource in ("lab-shell.css", "lab-shell.js", "business-demo.css", "demo-utils.js"):
        if not (DOCS / "site" / resource).exists():
            errors.append(f"missing generated shared lab resource {resource}")
    if errors:
        print("SITE CHECK FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"SITE CHECK PASSED: {len(MARKETING)} marketing pages and {len(LAB)} lab pages verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
