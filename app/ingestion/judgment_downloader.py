"""Respectful downloader for discoverable Supreme Court of India judgment PDFs.

Does not bypass CAPTCHA, login, or access controls. Historical official PDF URLs
may be listed in data/ingestion/official_judgment_urls.txt.
"""
from __future__ import annotations
import argparse, hashlib, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qs
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

HOME = "https://www.sci.gov.in/"
ALLOWED_HOSTS = {
    "www.sci.gov.in",
    "sci.gov.in",
    "cdn.s3waas.gov.in",
    "cdnbbsr.s3waas.gov.in",
}
USER_AGENT = "LegalMindAI-JudgmentResearch/1.0 (low-rate public-document retrieval)"
DOWNLOAD_DIR = Path("data/ingestion/downloaded")
MANIFEST = Path("data/ingestion/download_manifest.jsonl")
URLS_FILE = Path("data/ingestion/official_judgment_urls.txt")
MAX_BYTES = 80 * 1024 * 1024
TIMEOUT = (10, 40)


def allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme == "https" and (p.hostname or "").lower() in ALLOWED_HOSTS


def robots_allows(url: str) -> bool:
    p = urlparse(url)
    robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        r = requests.get(robots_url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        if r.status_code == 404:
            return True
        if not r.ok:
            print(f"Skipping (could not verify robots.txt, HTTP {r.status_code}): {url}")
            return False
        rp.parse(r.text.splitlines())
        return rp.can_fetch(USER_AGENT, url)
    except requests.RequestException as exc:
        print(f"Skipping (robots check failed: {exc}): {url}")
        return False


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*;q=0.8"})
    return s


def get_html(s: requests.Session, url: str) -> str | None:
    if not allowed(url) or not robots_allows(url):
        return None
    try:
        r = s.get(url, timeout=TIMEOUT, allow_redirects=True)
        if not r.ok or not allowed(r.url) or "text/html" not in r.headers.get("Content-Type", "").lower():
            return None
        return r.text
    except requests.RequestException as exc:
        print(f"Page fetch failed: {url} ({exc})")
        return None


def discover_pages(s: requests.Session) -> list[dict]:
    html = get_html(s, HOME)
    if not html:
        print("Could not read official SCI homepage; no pages discovered.")
        return []
    soup = BeautifulSoup(html, "html.parser")
    out, seen = [], set()
    for a in soup.select("a[href]"):
        url = urljoin(HOME, a.get("href", "").strip())
        p, q = urlparse(url), parse_qs(urlparse(url).query)
        if p.path.rstrip("/").endswith("/view-pdf") and q.get("type", [""])[0].lower() == "j" and allowed(url) and url not in seen:
            title = " ".join(a.get_text(" ", strip=True).split()) or f"Supreme_Court_Judgment_{len(out)+1}"
            out.append({"title": title, "url": url})
            seen.add(url)
    return out



def find_pdf_links(s: requests.Session, page_url: str) -> list[str]:
    """Find direct PDF links exposed by an official judgment page."""
    html = get_html(s, page_url)
    if not html:
        return []

    soup = BeautifulSoup(html, "html.parser")
    links: list[str] = []

    # Links and embedded document elements.
    for tag in soup.select(
        "a[href], iframe[src], embed[src], object[data], source[src]"
    ):
        raw = (
            tag.get("href")
            or tag.get("src")
            or tag.get("data")
            or ""
        ).strip()

        if not raw:
            continue

        url = urljoin(page_url, raw.replace("&amp;", "&"))
        content_type = (tag.get("type") or "").lower()

        if (
            allowed(url)
            and (
                urlparse(url).path.lower().endswith(".pdf")
                or "application/pdf" in content_type
            )
        ):
            links.append(url)

    # Some pages expose a PDF URL in JavaScript configuration.
    patterns = [
        r"""(?i)["'](?:file|pdf|pdfUrl|downloadUrl|documentUrl)["']\s*:\s*["']([^"']+\.pdf(?:\?[^"']*)?)["']""",
        r"""(?i)(https?://[^"'\\\s<>]+\.pdf(?:\?[^"'\\\s<>]*)?)""",
        r"""(?i)(/[^"'\\\s<>]+\.pdf(?:\?[^"'\\\s<>]*)?)""",
    ]

    for pattern in patterns:
        for raw in re.findall(pattern, html):
            url = urljoin(page_url, raw.replace("&amp;", "&"))
            if allowed(url) and urlparse(url).path.lower().endswith(".pdf"):
                links.append(url)

    # Preserve order and remove duplicates.
    return list(dict.fromkeys(links))

def read_seen() -> tuple[set[str], set[str]]:
    urls, hashes = set(), set()
    if MANIFEST.exists():
        for line in MANIFEST.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
                if row.get("source_url"): urls.add(row["source_url"])
                if row.get("sha256"): hashes.add(row["sha256"])
            except json.JSONDecodeError:
                pass
    return urls, hashes


def manual_urls() -> list[str]:
    if not URLS_FILE.exists(): return []
    return [line.strip() for line in URLS_FILE.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def safe_name(text: str) -> str:
    return (re.sub(r"[^A-Za-z0-9._-]+", "_", text).strip("._-") or "sci_judgment")[:100]


def download(s: requests.Session, url: str, title: str, seen_urls: set[str], seen_hashes: set[str], dry_run: bool) -> bool:
    if not allowed(url):
        print(f"SKIP unapproved host: {url}"); return False
    if url in seen_urls:
        print(f"SKIP already downloaded URL: {url}"); return False
    if not robots_allows(url):
        print(f"SKIP robots policy not confirmed/permitted: {url}"); return False
    if dry_run:
        print(f"DRY RUN: would download {url}"); return True
    try:
        with s.get(url, timeout=TIMEOUT, stream=True, allow_redirects=True) as r:
            r.raise_for_status()
            if not allowed(r.url):
                print(f"SKIP redirect outside approved hosts: {r.url}"); return False
            chunks, total = [], 0
            for chunk in r.iter_content(65536):
                if not chunk: continue
                total += len(chunk)
                if total > MAX_BYTES:
                    print(f"SKIP oversized file: {url}"); return False
                chunks.append(chunk)
            data = b"".join(chunks)
            if not data.startswith(b"%PDF-"):
                print(f"SKIP response is not a PDF: {url}"); return False
            digest = hashlib.sha256(data).hexdigest()
            if digest in seen_hashes:
                print(f"SKIP duplicate content (SHA-256): {url}")
                seen_urls.add(url); return False
            DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
            MANIFEST.parent.mkdir(parents=True, exist_ok=True)
            filename = f"{safe_name(title)}_{digest[:12]}.pdf"
            dest = DOWNLOAD_DIR / filename
            tmp = dest.with_suffix(".pdf.part")
            tmp.write_bytes(data); tmp.replace(dest)
            record = {"case_title": title, "court": "Supreme Court of India", "document_type": "Judgment", "source_url": r.url, "discovery_url": url, "downloaded_at": datetime.now(timezone.utc).isoformat(), "sha256": digest, "file_name": filename, "file_path": str(dest).replace("\\", "/"), "bytes": len(data)}
            with MANIFEST.open("a", encoding="utf-8") as f: f.write(json.dumps(record, ensure_ascii=False) + "\n")
            seen_urls.update({url, r.url}); seen_hashes.add(digest)
            print(f"DOWNLOADED {filename} ({len(data):,} bytes)")
            return True
    except requests.RequestException as exc:
        print(f"DOWNLOAD FAILED: {url} ({exc})"); return False


def run(max_downloads: int, delay: float, dry_run: bool, homepage: bool) -> int:
    s, seen_urls, seen_hashes = session(), *read_seen()
    candidates: list[tuple[str, str]] = []
    for url in manual_urls():
        if allowed(url): candidates.append((url, Path(urlparse(url).path).stem or "official_judgment"))
        else: print(f"Manual URL skipped (host not approved): {url}")
    if homepage:
        pages = discover_pages(s)
        print(f"Found {len(pages)} judgment entry page(s) linked from official SCI homepage.")
        for page in pages:
            time.sleep(delay)
            pdfs = find_pdf_links(s, page["url"])
            if pdfs:
                candidates.extend((pdf, page["title"]) for pdf in pdfs)
            else:
                print(f"PDF not discoverable without browser interaction; manual review: {page['url']}")
    unique, seen = [], set()
    for url, title in candidates:
        if url not in seen: unique.append((url, title)); seen.add(url)
    count = 0
    for url, title in unique:
        if count >= max_downloads: break
        if not urlparse(url).path.lower().endswith(".pdf"):
            pdfs = find_pdf_links(s, url)
            if not pdfs:
                print(f"No direct PDF found; skipped without bypassing access controls: {url}"); continue
        else: pdfs = [url]
        for pdf in pdfs:
            if count >= max_downloads: break
            if download(s, pdf, title, seen_urls, seen_hashes, dry_run): count += 1
            time.sleep(delay)
    print(f"\nRun complete. New PDFs {'planned' if dry_run else 'downloaded'}: {count}")
    print(f"Download directory: {DOWNLOAD_DIR}\nManifest: {MANIFEST}")
    print("This does not establish complete 1947-present historical coverage.")
    return count


def main() -> None:
    p = argparse.ArgumentParser(description="Download discoverable official Supreme Court judgment PDFs.")
    p.add_argument("--max-downloads", type=int, default=5)
    p.add_argument("--delay", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--no-homepage", action="store_true", help="Only process official URLs from the manual URL list")
    a = p.parse_args()
    if a.max_downloads < 1: p.error("--max-downloads must be >= 1")
    if a.delay < 1: p.error("--delay must be >= 1 second")
    run(a.max_downloads, a.delay, a.dry_run, not a.no_homepage)

if __name__ == "__main__": main()
