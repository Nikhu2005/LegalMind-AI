"""Search recent judgments linked from the official Supreme Court website.

This deliberately does not automate CAPTCHA-protected judgment search portals.
For each request it inspects a small number of judgment pages linked from the
SCI homepage, reads linked PDFs in memory, and returns only matching passages.
No PDF, metadata, or index is written to disk.
"""
from __future__ import annotations

import re
import time
from urllib.robotparser import RobotFileParser
from urllib.parse import parse_qs, urljoin, urlparse

import fitz
import requests
from bs4 import BeautifulSoup

from app.ingestion.judgment_downloader import (
    ALLOWED_HOSTS,
    HOME,
    USER_AGENT,
)


REQUEST_TIMEOUT = (4, 12)
MAX_LISTING_PAGES = 10
MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_HTML_BYTES = 2 * 1024 * 1024
MAX_PDF_PAGES = 500
MAX_EXCERPT_CHARS = 1800
SCI_SOURCE_HOSTS = ALLOWED_HOSTS | {"api.sci.gov.in", "webapi.sci.gov.in"}

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "case",
    "cases", "court", "courts", "do", "does", "for", "from", "give",
    "how", "i", "in", "india", "indian", "is", "it", "judgment",
    "judgments", "me", "of", "on", "or", "please", "search", "show",
    "say", "says", "tell", "that", "the", "their", "this", "to", "under", "was",
    "what", "when", "where", "which", "who", "why", "with",
    "v", "versus", "vs",
}


def _allowed_source_url(url: str) -> bool:
    parsed = urlparse(url)
    return (
        parsed.scheme == "https"
        and (parsed.hostname or "").lower() in SCI_SOURCE_HOSTS
    )


def _robots_allows(
    session: requests.Session,
    url: str,
    cache: dict[str, RobotFileParser | None],
) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if not _allowed_source_url(url) or host not in SCI_SOURCE_HOSTS:
        return False

    if host not in cache:
        robots_url = f"https://{host}/robots.txt"
        try:
            with session.get(
                robots_url,
                timeout=REQUEST_TIMEOUT,
                allow_redirects=False,
            ) as response:
                if response.status_code == 404:
                    parser = RobotFileParser()
                    parser.parse([])
                    cache[host] = parser
                elif response.ok:
                    parser = RobotFileParser()
                    parser.parse(response.text.splitlines())
                    cache[host] = parser
                else:
                    cache[host] = None
        except requests.RequestException:
            cache[host] = None

    parser = cache[host]
    return parser is not None and parser.can_fetch(USER_AGENT, url)


def _request_allowed(
    session: requests.Session,
    url: str,
    robots_cache: dict[str, RobotFileParser | None],
) -> requests.Response | None:
    current_url = url
    for _ in range(4):
        if not _robots_allows(session, current_url, robots_cache):
            return None
        response = session.get(
            current_url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            stream=True,
        )
        if response.status_code not in {301, 302, 303, 307, 308}:
            return response
        location = response.headers.get("Location")
        response.close()
        if not location:
            return None
        current_url = urljoin(current_url, location)
    return None


def _read_limited(response: requests.Response, limit: int) -> bytes | None:
    content_length = response.headers.get("Content-Length")
    if content_length:
        try:
            if int(content_length) > limit:
                return None
        except ValueError:
            pass

    body = bytearray()
    for block in response.iter_content(64 * 1024):
        if not block:
            continue
        body.extend(block)
        if len(body) > limit:
            return None
    return bytes(body)


def _fetch_html(
    session: requests.Session,
    url: str,
    robots_cache: dict[str, RobotFileParser | None],
) -> str | None:
    try:
        response = _request_allowed(session, url, robots_cache)
        if response is None:
            return None
        with response:
            if not response.ok or not _allowed_source_url(response.url):
                return None
            content_type = response.headers.get("Content-Type", "").lower()
            if content_type and "text/html" not in content_type:
                return None
            body = _read_limited(response, MAX_HTML_BYTES)
            if body is None:
                return None
            encoding = response.encoding or "utf-8"
            return body.decode(encoding, errors="replace")
    except requests.RequestException:
        return None


def _discover_judgment_pages(
    session: requests.Session,
    robots_cache: dict[str, RobotFileParser | None],
) -> list[dict[str, str]]:
    html = _fetch_html(session, HOME, robots_cache)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    pages: list[dict[str, str]] = []
    seen: set[str] = set()
    for anchor in soup.select("a[href]"):
        url = urljoin(HOME, anchor.get("href", "").strip())
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        if (
            parsed.path.rstrip("/").endswith("/view-pdf")
            and query.get("type", [""])[0].lower() == "j"
            and _allowed_source_url(url)
            and url not in seen
        ):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            pages.append({"title": title, "url": url})
            seen.add(url)
            if len(pages) >= MAX_LISTING_PAGES:
                break
    return pages


def _find_pdf_urls(
    session: requests.Session,
    page_url: str,
    robots_cache: dict[str, RobotFileParser | None],
) -> list[str]:
    html = _fetch_html(session, page_url, robots_cache)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []
    for tag in soup.select("a[href], iframe[src], embed[src], object[data], source[src]"):
        raw = (tag.get("href") or tag.get("src") or tag.get("data") or "").strip()
        if not raw:
            continue
        url = urljoin(page_url, raw.replace("&amp;", "&"))
        content_type = (tag.get("type") or "").lower()
        if _allowed_source_url(url) and (
            urlparse(url).path.lower().endswith(".pdf")
            or "application/pdf" in content_type
        ):
            links.append(url)

    patterns = (
        r"(?i)[\"'](?:file|pdf|pdfUrl|downloadUrl|documentUrl)[\"']\s*:\s*[\"']([^\"']+\.pdf(?:\?[^\"']*)?)",
        r"(?i)(https?://[^\"'\\\s<>]+\.pdf(?:\?[^\"'\\\s<>]*)?)",
        r"(?i)(/[^\"'\\\s<>]+\.pdf(?:\?[^\"'\\\s<>]*)?)",
    )
    for pattern in patterns:
        for raw in re.findall(pattern, html):
            url = urljoin(page_url, raw.replace("&amp;", "&"))
            if _allowed_source_url(url):
                links.append(url)
    return list(dict.fromkeys(links))


def _fetch_pdf(
    session: requests.Session,
    url: str,
    robots_cache: dict[str, RobotFileParser | None],
) -> bytes | None:
    try:
        response = _request_allowed(session, url, robots_cache)
        if response is None:
            return None
        with response:
            if not response.ok or not _allowed_source_url(response.url):
                return None
            body = _read_limited(response, MAX_PDF_BYTES)
            if body is None or not body.startswith(b"%PDF-"):
                return None
            return body
    except requests.RequestException:
        return None


def _query_terms(query: str) -> list[str]:
    terms: list[str] = []
    for term in re.findall(r"[\w]+", query.casefold()):
        if len(term) > 1 and term not in STOPWORDS and term not in terms:
            terms.append(term)
    return terms


def _extract_metadata(text: str, title: str) -> dict[str, str | None]:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    case_name = None
    case_pattern = re.compile(r"(.{2,150}?)\s+(?:VERSUS|VS\.?|V\.?)\s+(.{2,150})", re.I)
    for line in lines:
        if len(line) > 300:
            continue
        match = case_pattern.search(line)
        if match:
            case_name = f"{match.group(1).strip()} v. {match.group(2).strip()}"
            break
    if not case_name and title and re.search(r"(?:\bversus\b|\bvs?\.?\s)", title, re.I):
        case_name = title.strip()

    case_number_match = re.search(
        r"\b(?:Civil Appeal|Criminal Appeal|Writ Petition|Special Leave Petition|SLP\s*\(C\)|Diary)\s*(?:No\.?|Number)?\s*[^\n]{0,100}",
        text,
        re.I,
    )
    date_match = re.search(
        r"\b(?:Date\s*:\s*)?(\d{1,2}[./-]\d{1,2}[./-]\d{4}|\d{1,2}\s+[A-Za-z]+\s+\d{4})\b",
        text,
        re.I,
    )
    citation_match = re.search(r"\b\d{4}\s+INSC\s+\d+\b", text, re.I)

    return {
        "case_name": case_name,
        "court": "Supreme Court of India",
        "judgment_date": date_match.group(1) if date_match else None,
        "case_number": case_number_match.group(0).strip() if case_number_match else None,
        "citation": citation_match.group(0) if citation_match else None,
    }


def _matching_excerpt(
    pages: list[str], terms: list[str]
) -> tuple[list[str], str, int | None]:
    all_matched: set[str] = set()
    first_hit: tuple[str, int] | None = None
    best_page_text = ""
    best_page_number: int | None = None
    best_page_hits = -1

    for page_number, page_text in enumerate(pages, start=1):
        if not page_text.strip():
            continue
        page_lower = page_text.casefold()
        page_hits = 0
        for term in terms:
            count = len(re.findall(rf"(?<!\w){re.escape(term)}(?!\w)", page_lower))
            if count:
                all_matched.add(term)
                page_hits += count
                if first_hit is None:
                    first_hit = (page_text, page_number)
        if page_hits > best_page_hits:
            best_page_hits = page_hits
            best_page_text = page_text
            best_page_number = page_number

    matched_terms = [term for term in terms if term in all_matched]
    if first_hit:
        best_page_text, best_page_number = first_hit
    if not matched_terms:
        return [], "", None

    clean_text = " ".join(best_page_text.split())
    lower_text = clean_text.casefold()
    positions = [lower_text.find(term) for term in matched_terms if lower_text.find(term) >= 0]
    start_at = min(positions) if positions else 0
    start = max(0, start_at - MAX_EXCERPT_CHARS // 3)
    end = min(len(clean_text), start + MAX_EXCERPT_CHARS)
    excerpt = clean_text[start:end]
    if start > 0:
        excerpt = "…" + excerpt
    if end < len(clean_text):
        excerpt += "…"
    return matched_terms, excerpt, best_page_number


def search_recent_sci_judgments(query: str, max_results: int = 10) -> dict:
    """Search a bounded set of recent SCI homepage-linked judgment PDFs.

    This is a live, ephemeral scan, not a query against the court's historical
    search database. CAPTCHA-protected portals are not automated.
    """
    terms = _query_terms(query)
    if not terms:
        return {
            "results": [],
            "source_pages_scanned": 0,
            "pdfs_examined": 0,
            "warnings": ["Enter at least one searchable term."],
        }

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/pdf,*/*;q=0.8",
        }
    )
    robots_cache: dict[str, RobotFileParser | None] = {}
    warnings: list[str] = []
    pages = _discover_judgment_pages(session, robots_cache)
    if not pages:
        warnings.append(
            "No judgment pages were discoverable from the official SCI homepage. "
            "The site may be unavailable, may have changed its page format, or robots policy may disallow access."
        )
        session.close()
        return {
            "results": [],
            "source_pages_scanned": 0,
            "pdfs_examined": 0,
            "warnings": warnings,
        }

    results: list[dict] = []
    pdfs_examined = 0
    pages_scanned = 0
    seen_pdfs: set[str] = set()

    for listing in pages:
        if pdfs_examined >= MAX_LISTING_PAGES:
            break
        pages_scanned += 1
        pdf_urls = _find_pdf_urls(session, listing["url"], robots_cache)
        if not pdf_urls:
            continue

        pdf_url = next((url for url in pdf_urls if url not in seen_pdfs), None)
        if not pdf_url:
            continue
        seen_pdfs.add(pdf_url)
        time.sleep(0.25)
        pdf_bytes = _fetch_pdf(session, pdf_url, robots_cache)
        if not pdf_bytes:
            continue
        pdfs_examined += 1

        try:
            with fitz.open(stream=pdf_bytes, filetype="pdf") as document:
                page_count = len(document)
                text_scan_truncated = page_count > MAX_PDF_PAGES
                metadata_text = "\n".join(
                    document[index].get_text("text")
                    for index in range(min(5, page_count))
                )
                metadata = _extract_metadata(metadata_text, listing.get("title", ""))
                searchable_pages = [
                    document[index].get_text("text")
                    for index in range(min(page_count, MAX_PDF_PAGES))
                ]
        except (fitz.FileDataError, RuntimeError, ValueError):
            continue

        matched_terms, excerpt, page_number = _matching_excerpt(searchable_pages, terms)
        case_name = metadata["case_name"]
        if not matched_terms and case_name:
            title_matches = [term for term in terms if term in case_name.casefold()]
            if title_matches:
                matched_terms = title_matches
                excerpt = " ".join(" ".join(searchable_pages).split())[:MAX_EXCERPT_CHARS]
                page_number = None
        if not matched_terms:
            continue

        results.append(
            {
                **metadata,
                "document_type": "Judgment",
                "source_url": listing["url"],
                "pdf_url": pdf_url,
                "page_count": page_count,
                "text_scan_truncated": text_scan_truncated,
                "page_number": page_number,
                "text": excerpt,
                "matched_terms": matched_terms,
            }
        )

    if pdfs_examined == 0:
        warnings.append(
            "No accessible judgment PDFs were found in the discovered pages; the source may have changed or robots policy may disallow access."
        )
    results.sort(key=lambda item: len(item["matched_terms"]), reverse=True)
    session.close()
    return {
        "results": results[: max(1, min(int(max_results), 20))],
        "source_pages_scanned": pages_scanned,
        "pdfs_examined": pdfs_examined,
        "warnings": warnings,
    }
