"""Reads a company's public website so the chat can say what the business does (FR-8.1).

Fetched by our own server with guards against reaching anything private: https only,
public addresses only (checked on every redirect), a short timeout and a size cap.
Only the title, description and a little visible text are kept.
"""

import html
import ipaddress
import re
import socket
from urllib.parse import urljoin, urlsplit

import httpx

MAX_BYTES = 500_000
MAX_TEXT = 3000
TIMEOUT = 5.0
FREE_MAIL = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "hotmail.com",
        "hotmail.co.uk",
        "outlook.com",
        "live.com",
        "yahoo.com",
        "yahoo.co.uk",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "btinternet.com",
        "sky.com",
        "gmx.com",
        "example.com",
    }
)


class WebsiteError(Exception):
    pass


def guess_from_email(email: str) -> str | None:
    domain = email.rsplit("@", 1)[-1].lower()
    if (
        domain in FREE_MAIL
        or domain.endswith((".example.com", ".test", ".local"))
        or "." not in domain
    ):
        return None
    return f"https://{domain}"


def normalise(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise WebsiteError("Only https websites can be read.")
    return f"https://{parts.hostname}{parts.path or '/'}"


def _public(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise WebsiteError("That website could not be found.") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise WebsiteError("That website is not on the public internet.")


def _text(page: str) -> str:
    title = re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    desc = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']*)', page, re.I)
    body = re.sub(r"<head[^>]*>.*?</head>", " ", page, flags=re.S | re.I)
    body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", body, flags=re.S | re.I)
    body = re.sub(r"<[^>]+>", " ", body)
    parts = [title.group(1) if title else "", desc.group(1) if desc else "", body]
    text = html.unescape(" ".join(" ".join(p.split()) for p in parts if p))
    return text[:MAX_TEXT]


def fetch(url: str) -> str:
    url = normalise(url)
    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=False,
        headers={"User-Agent": "BoardRoom.io setup (+https://boardroom.io)"},
    ) as client:
        for _ in range(4):
            host = urlsplit(url).hostname or ""
            _public(host)
            with client.stream("GET", url) as r:
                if r.is_redirect:
                    url = normalise(urljoin(url, r.headers.get("location", "")))
                    continue
                if r.status_code != 200 or "html" not in r.headers.get("content-type", ""):
                    raise WebsiteError("That website did not return a page.")
                body = b""
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        break
                return _text(body.decode(r.encoding or "utf-8", errors="replace"))
    raise WebsiteError("That website redirects too many times.")
