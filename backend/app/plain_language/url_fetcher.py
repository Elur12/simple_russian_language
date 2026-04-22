"""
Fetch a public webpage and extract its readable text content.

Security: blocks SSRF by rejecting private/loopback IPs before connecting.
"""

import ipaddress
import socket
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup, Tag

FETCH_TIMEOUT = 15
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB
MAX_TEXT_CHARS = 40_000

# Tags whose content we drop entirely
_DROP_TAGS = {
    "script", "style", "noscript", "nav", "header", "footer",
    "aside", "form", "button", "iframe", "svg", "figure",
    "figcaption", "menu", "dialog",
}

# Tags we treat as paragraph boundaries
_BLOCK_TAGS = {
    "p", "h1", "h2", "h3", "h4", "h5", "h6",
    "li", "td", "th", "blockquote", "pre", "dd", "dt",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PlainLanguageChecker/1.0; "
        "+https://github.com/plain-language-checker)"
    ),
    "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru,en;q=0.9",
}


class UrlFetchError(Exception):
    pass


def _validate_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise UrlFetchError("Поддерживаются только HTTP и HTTPS ссылки.")
    if not parsed.hostname:
        raise UrlFetchError("Некорректный URL: не указан хост.")

    # SSRF protection: resolve hostname and check IP
    try:
        ip_str = socket.gethostbyname(parsed.hostname)
        ip = ipaddress.ip_address(ip_str)
    except socket.gaierror:
        raise UrlFetchError(f"Не удалось разрешить хост: {parsed.hostname}")

    if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
        raise UrlFetchError("Ссылки на внутренние адреса недопустимы.")


def _extract_text(soup: BeautifulSoup) -> str:
    # Remove non-content elements
    for tag in soup.find_all(_DROP_TAGS):
        tag.decompose()

    # Prefer <article> or <main>; fall back to <body>
    root: Tag = (
        soup.find("article")
        or soup.find("main")
        or soup.find("body")
        or soup
    )

    paragraphs: list[str] = []

    for el in root.find_all(_BLOCK_TAGS):
        text = el.get_text(separator=" ", strip=True)
        text = " ".join(text.split())  # collapse whitespace
        if len(text) >= 30:            # skip fragments that are too short
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def fetch_url(url: str) -> dict:
    """
    Fetch a URL and return {"title": str, "text": str, "url": str}.

    Raises UrlFetchError on any failure.
    """
    _validate_url(url)

    try:
        resp = requests.get(
            url,
            headers=_HEADERS,
            timeout=FETCH_TIMEOUT,
            stream=True,
        )
        resp.raise_for_status()

        content_type = resp.headers.get("Content-Type", "")
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise UrlFetchError(
                f"Страница вернула неподдерживаемый тип контента: {content_type}"
            )

        # Encoding must be read from headers BEFORE consuming the body stream.
        # resp.apparent_encoding reads resp.content (already consumed) — don't use it.
        encoding = resp.encoding or "utf-8"

        # Read with size limit
        chunks: list[bytes] = []
        total = 0
        for chunk in resp.iter_content(chunk_size=32768):
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                break
            chunks.append(chunk)
        html = b"".join(chunks).decode(encoding, errors="replace")

    except requests.exceptions.Timeout:
        raise UrlFetchError("Страница не ответила за отведённое время.")
    except requests.exceptions.ConnectionError:
        raise UrlFetchError("Не удалось подключиться к странице.")
    except requests.exceptions.HTTPError as e:
        raise UrlFetchError(f"Страница вернула ошибку: HTTP {e.response.status_code}.")

    soup = BeautifulSoup(html, "lxml")

    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    text = _extract_text(soup)

    if not text.strip():
        raise UrlFetchError("Не удалось извлечь текст из страницы. Возможно, контент загружается через JavaScript.")

    # Truncate if too long
    if len(text) > MAX_TEXT_CHARS:
        text = text[:MAX_TEXT_CHARS].rsplit("\n\n", 1)[0]

    return {"title": title, "text": text, "url": url}
