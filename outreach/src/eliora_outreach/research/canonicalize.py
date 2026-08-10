from __future__ import annotations

import hashlib
import ipaddress
import socket
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

tldextract: Any = None
try:
    import tldextract as _tldextract

    tldextract = _tldextract
except ImportError:  # pragma: no cover
    pass

TRACKING_KEYS = {
    "gclid",
    "fbclid",
    "mc_cid",
    "mc_eid",
    "ref",
    "source",
    "utm_campaign",
    "utm_medium",
    "utm_source",
    "utm_term",
}
SOCIAL_HOSTS = {
    "linkedin.com",
    "www.linkedin.com",
    "facebook.com",
    "www.facebook.com",
    "x.com",
    "twitter.com",
    "instagram.com",
}
RESERVED_HOST_SUFFIXES = (".example", ".invalid", ".test", ".localhost")
DIRECTORY_HOSTS = {
    "crunchbase.com",
    "www.crunchbase.com",
    "zoominfo.com",
    "www.zoominfo.com",
    "apollo.io",
    "www.apollo.io",
    "hunter.io",
    "www.hunter.io",
}


def registrable_domain(value: str) -> str:
    candidate = value if "://" in value else f"https://{value}"
    host = (urlparse(candidate).hostname or "").lower().rstrip(".")
    if tldextract:
        extracted = tldextract.extract(host)
        return ".".join(part for part in (extracted.domain, extracted.suffix) if part).lower()
    pieces = host.split(".")
    return ".".join(pieces[-2:]) if len(pieces) >= 2 else host


def canonicalize_url(value: str, base: str | None = None) -> str:
    absolute = urljoin(base, value) if base else value
    parsed = urlparse(absolute)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only HTTP(S) URLs with a hostname are allowed")
    query = [
        (key, val)
        for key, val in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in TRACKING_KEYS
    ]
    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/")
    return urlunparse(
        (parsed.scheme.lower(), parsed.hostname.lower(), path, "", urlencode(query), "")
    )


def url_hash(value: str) -> str:
    return hashlib.sha256(canonicalize_url(value).encode()).hexdigest()


def is_social_url(value: str) -> bool:
    host = (urlparse(value).hostname or "").lower().rstrip(".")
    return host in SOCIAL_HOSTS or any(host.endswith(f".{root}") for root in SOCIAL_HOSTS)


def is_reserved_domain(value: str) -> bool:
    host = (urlparse(value if "://" in value else f"https://{value}").hostname or "").lower()
    if not host:
        return True
    if host == "localhost" or host.endswith(RESERVED_HOST_SUFFIXES):
        return True
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def is_directory_or_data_broker(value: str) -> bool:
    host = (urlparse(value if "://" in value else f"https://{value}").hostname or "").lower()
    return host in DIRECTORY_HOSTS or any(host.endswith(f".{root}") for root in DIRECTORY_HOSTS)


def is_private_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or str(ip) in {"169.254.169.254", "100.100.100.200"}
    )


def resolve_public_hosts(hostname: str) -> list[str]:
    addresses = {
        str(item[4][0]) for item in socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    }
    if not addresses or any(is_private_ip(address) for address in addresses):
        raise ValueError(f"URL resolves to a private, local, or metadata address: {hostname}")
    return sorted(addresses)


def validate_public_url(value: str, *, resolve: bool = True) -> str:
    canonical = canonicalize_url(value)
    if is_reserved_domain(canonical):
        raise ValueError("Reserved, placeholder, localhost, or raw-IP domains are not eligible")
    if is_social_url(canonical):
        raise ValueError("Social-network URLs are not eligible research sources")
    if is_directory_or_data_broker(canonical):
        raise ValueError("Directories and data-broker domains are not eligible research sources")
    host = urlparse(canonical).hostname
    if resolve and host:
        resolve_public_hosts(host)
    return canonical
