from __future__ import annotations

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser


def allowed_by_robots(url: str, user_agent: str, *, fetcher=None) -> bool:
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    try:
        if fetcher:
            parser.parse(fetcher(robots_url).splitlines())
        else:
            parser.read()
        return parser.can_fetch(user_agent, url)
    except Exception:
        return False
