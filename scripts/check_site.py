#!/usr/bin/env python3
"""Small, dependency-free regression checks for the rendered marketing site."""

from __future__ import annotations

import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
MARKETING_PAGES = ["index.html", "services.html", "work.html", "about.html", "contact.html"]


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tags: list[tuple[str, dict[str, str]]] = []
        self.text_stack: list[str] = []
        self.links: list[tuple[str, str, str]] = []
        self.images: list[dict[str, str]] = []
        self.headings: list[tuple[str, str]] = []
        self.title = ""
        self.description = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key: value or "" for key, value in attrs}
        self.tags.append((tag, attr_map))
        self.text_stack.append("")
        if tag == "a":
            self.links.append((attr_map.get("href", ""), "", attr_map.get("aria-label", "")))
        if tag == "img":
            self.images.append(attr_map)
        if tag == "title":
            self.text_stack[-1] = ""

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_data(self, data: str) -> None:
        if self.text_stack:
            self.text_stack[-1] += data

    def handle_endtag(self, tag: str) -> None:
        text = self.text_stack.pop().strip() if self.text_stack else ""
        if tag == "a" and self.links:
            href, _, aria_label = self.links[-1]
            self.links[-1] = (href, " ".join(text.split()), aria_label)
        if tag == "title":
            self.title = " ".join(text.split())


def local_target(value: str, source: Path) -> Path | None:
    if not value or value.startswith(("#", "mailto:", "tel:", "data:", "javascript:")):
        return None
    parsed = urlparse(value)
    if parsed.scheme or parsed.netloc:
        return None
    return (source.parent / parsed.path).resolve()


def check_page(path: Path) -> list[str]:
    parser = SiteParser()
    parser.feed(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    html = path.read_text(encoding="utf-8")
    tags = [tag for tag, _ in parser.tags]
    attrs = [attrs for _, attrs in parser.tags]

    if not parser.title:
        errors.append(f"{path.name}: missing page title")
    if 'name="description"' not in html and "name='description'" not in html:
        errors.append(f"{path.name}: missing meta description")
    if 'rel="canonical"' not in html:
        errors.append(f"{path.name}: missing canonical URL")
    if html.count("<h1") != 1:
        errors.append(f"{path.name}: expected exactly one h1, found {html.count('<h1')}")
    for required in ("header", "main", "footer"):
        if required not in tags:
            errors.append(f"{path.name}: missing {required} landmark")
    if "class=\"skip-link\"" not in html and "class='skip-link'" not in html:
        errors.append(f"{path.name}: missing skip link")
    for image in parser.images:
        if "alt" not in image:
            errors.append(f"{path.name}: image missing alt attribute ({image.get('src', 'unknown')})")
    for href, text, aria_label in parser.links:
        if not href or href in ("#", "#0"):
            errors.append(f"{path.name}: empty or placeholder link")
        if not text and not aria_label and not href.startswith("#"):
            errors.append(f"{path.name}: link without accessible text ({href})")
        target = local_target(href, path)
        if target and not target.exists():
            errors.append(f"{path.name}: missing local link target {href}")
    for attrs in parser.tags:
        tag, values = attrs
        if tag in ("script", "link") and values.get("src", "").lower().endswith((".js", ".mjs")):
            target = local_target(values["src"], path)
            if target and not target.exists():
                errors.append(f"{path.name}: missing local script target {values['src']}")
        if tag == "script" and values.get("src"):
            source = values["src"].lower()
            if "vanta" in source or "three" in source:
                errors.append(f"{path.name}: forbidden Vanta/Three script reference")
    if "vanta" in html.lower() or "three.js" in html.lower() or "three.min" in html.lower():
        errors.append(f"{path.name}: forbidden Vanta/Three reference")
    if any(token in html.lower() for token in ("lorem ipsum", "example.com", "your-email", "href=\"#\"")):
        errors.append(f"{path.name}: placeholder content or URL found")
    return errors


def main() -> int:
    errors: list[str] = []
    cname = DOCS / "CNAME"
    if not cname.exists() or cname.read_text(encoding="utf-8").strip() != "elioratechsolutions.com":
        errors.append("docs/CNAME is missing or does not contain elioratechsolutions.com")
    for page in MARKETING_PAGES:
        path = DOCS / page
        if not path.exists():
            errors.append(f"missing generated marketing page: docs/{page}")
            continue
        errors.extend(check_page(path))
    if errors:
        print("SITE CHECK FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"SITE CHECK PASSED: {len(MARKETING_PAGES)} marketing pages and docs/CNAME verified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
