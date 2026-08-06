# =============================================================================
# webscraper.py
# -----------------------------------------------------------------------------
# Copyright 2025 Brian McBride at Tiki-1 Studio
# WHAT THIS FILE DOES
#   A same-domain website crawler: starting from one URL, it follows links
#   across the site (breadth-first), reading each page's title, visible text,
#   and outgoing links, and stores what it found in `cortex_scrape.db`. Stops once
#   it hits either cap you gave it: a max number of distinct URL "folders"
#   (first path segment, e.g. /docs/... vs /blog/...) or a max total number
#   of pages scanned.
#
# WHAT IT INTERACTS WITH
#   - `cortex_database.py`, where every run's settings/progress (one
#     `web_scrape_jobs` row) and every page it reads (one `web_scrape_data`
#     row each) get stored.
#   - The target website itself, over plain HTTP(S) GET requests -- this
#     reads publicly served pages exactly like a browser would, it does not
#     log in or submit anything.
#
# KEY FUNCTIONALITY NOTES
#   - Stays on the exact starting hostname only -- it will not follow a link
#     to a different site or a different subdomain.
#   - Respects the target site's robots.txt and pauses briefly between
#     requests, so it doesn't hammer the server it's reading from.
#   - "Folder" caps growth of *new* sections of the site, not how many pages
#     from an already-seen folder can be read -- once the cap is hit, pages
#     already queued from known folders still get scanned up to the file cap.
# =============================================================================

import sys
import time
from collections import deque
from pathlib import Path
from typing import Optional, Set
from urllib.parse import urljoin, urlparse, urldefrag
from urllib.robotparser import RobotFileParser

import requests
from lxml import html as lxml_html

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parents[1]
CORE_DIR = PARENT_DIR / "00_System"

if str(CORE_DIR) not in sys.path:
    sys.path.append(str(CORE_DIR))

from cortex_database import get_db_connection, initialize_database

USER_AGENT = "Cortex-WebScraper/1.0 (+internal indexing tool)"
REQUEST_TIMEOUT = 10
REQUEST_DELAY_SECONDS = 0.5


def url_folder(url: str) -> str:
    """The first path segment of a URL, e.g. '/docs/intro' -> 'docs'. Root-level
    pages (no path segment) all share the folder key '' (the site root)."""
    segments = [s for s in urlparse(url).path.split("/") if s]
    return segments[0] if segments else ""


class WebScraper:
    def __init__(self, seed_url: str, max_folders: int, max_files: int):
        self.seed_url = seed_url
        self.max_folders = max_folders
        self.max_files = max_files
        self.hostname = urlparse(seed_url).hostname

        self.session = requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT

        self.robots = RobotFileParser()
        self.robots.set_url(urljoin(seed_url, "/robots.txt"))
        try:
            self.robots.read()
        except Exception:
            pass  # No reachable robots.txt -- proceed as if everything's allowed.

    def _is_same_site(self, url: str) -> bool:
        return urlparse(url).hostname == self.hostname

    def _allowed_by_robots(self, url: str) -> bool:
        try:
            return self.robots.can_fetch(USER_AGENT, url)
        except Exception:
            return True

    def _fetch(self, url: str) -> Optional[lxml_html.HtmlElement]:
        try:
            response = self.session.get(url, timeout=REQUEST_TIMEOUT)
            content_type = response.headers.get("Content-Type", "")
            if response.status_code != 200 or "text/html" not in content_type:
                return None
            return lxml_html.fromstring(response.content)
        except Exception:
            return None

    def run(self) -> dict:
        report = {"success": True, "pages_scanned": 0, "folders_seen": 0, "errors": []}

        initialize_database()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO web_scrape_jobs (seed_url, max_folders, max_files) VALUES (?, ?, ?);",
            (self.seed_url, self.max_folders, self.max_files),
        )
        job_id = cursor.lastrowid
        conn.commit()

        visited: Set[str] = set()
        folders_seen: Set[str] = set()
        queue: deque = deque([self.seed_url])

        try:
            while queue and len(visited) < self.max_files:
                url = queue.popleft()
                if url in visited:
                    continue

                folder = url_folder(url)
                if folder not in folders_seen and len(folders_seen) >= self.max_folders:
                    continue  # New section of the site, but the folder cap is already full.

                if not self._allowed_by_robots(url):
                    report["errors"].append(f"Skipped (robots.txt disallows): {url}")
                    continue

                tree = self._fetch(url)
                visited.add(url)
                time.sleep(REQUEST_DELAY_SECONDS)

                if tree is None:
                    report["errors"].append(f"Could not read: {url}")
                    continue

                folders_seen.add(folder)

                title_nodes = tree.xpath("//title/text()")
                title = title_nodes[0].strip() if title_nodes else ""

                for tag in tree.xpath("//script | //style"):
                    tag.drop_tree()
                body_nodes = tree.xpath("//body")
                content = body_nodes[0].text_content() if body_nodes else tree.text_content()
                content = " ".join(content.split())  # Collapse whitespace/newlines.

                links = set()
                for href in tree.xpath("//a/@href"):
                    absolute_url, _ = urldefrag(urljoin(url, href))
                    if self._is_same_site(absolute_url) and absolute_url not in visited:
                        links.add(absolute_url)
                        queue.append(absolute_url)

                cursor.execute(
                    """INSERT OR REPLACE INTO web_scrape_data (job_id, url, title, content, links_found)
                       VALUES (?, ?, ?, ?, ?);""",
                    (job_id, url, title, content, len(links)),
                )
                conn.commit()

                report["pages_scanned"] = len(visited)
                report["folders_seen"] = len(folders_seen)
                print(f"[{len(visited)}/{self.max_files}] Scanned: {url} ({len(links)} links found)")

            cursor.execute(
                """UPDATE web_scrape_jobs
                   SET status = 'complete', pages_scanned = ?, folders_seen = ?, finished = datetime('now')
                   WHERE id = ?;""",
                (report["pages_scanned"], report["folders_seen"], job_id),
            )
            conn.commit()

        except Exception as e:
            report["success"] = False
            report["errors"].append(f"Scrape aborted: {e}")
            cursor.execute(
                "UPDATE web_scrape_jobs SET status = 'failed', finished = datetime('now') WHERE id = ?;",
                (job_id,),
            )
            conn.commit()

        finally:
            conn.close()

        return report


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print({"success": False, "errors": ["Usage: webscraper.py <url> <max_folders> <max_files>"]})
        sys.exit(1)

    seed_url, max_folders_arg, max_files_arg = sys.argv[1], sys.argv[2], sys.argv[3]
    scraper = WebScraper(seed_url, int(max_folders_arg), int(max_files_arg))
    print(scraper.run())
