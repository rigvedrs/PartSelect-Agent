"""Scrape PartSelect blog articles filtered for refrigerator/dishwasher topics."""
from __future__ import annotations

import csv
import json
import random
import re
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from scrapers import browser, io_utils

SITE = "https://www.partselect.com"
BLOG_INDEX = f"{SITE}/content/blog"
TOPIC_KEYWORDS = (
    "fridge",
    "refrigerator",
    "freezer",
    "dishwasher",
    "washer",
    "washing machine",
    "ice",
    "cooling",
    "temperature",
)

WRAPPER_SELECTORS = [
    ".blog__article-page_content",
    ".blog__article-page .blog__article-page_content",
    ".blog__article-page",
    "main.container article",
    "article",
]
TITLE_SELECTORS = [
    ".blog__article-page_content h1",
    ".blog__article-page h1",
    "main.container article h1",
    "article h1",
    "h1",
]
_YT_ID = re.compile(r"([a-zA-Z0-9_-]{6,})")


def _human_pause(lo: float = 0.4, hi: float = 0.9) -> None:
    time.sleep(random.uniform(lo, hi))


def _access_denied(driver: webdriver.Chrome) -> bool:
    try:
        title = (driver.title or "").lower()
        body = (driver.find_element(By.TAG_NAME, "body").text or "").lower()
        return "access denied" in title or "access denied" in body
    except Exception:
        return False


def _safe_get(driver: webdriver.Chrome, url: str, retries: int = 2) -> bool:
    for _ in range(retries + 1):
        driver.get(url)
        WebDriverWait(driver, 5).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
        browser.dismiss_overlays(driver)
        if not _access_denied(driver):
            return True
        _human_pause(0.4, 1.0)
    return False


def _youtube_watch(url_or_id: str) -> str | None:
    u = (url_or_id or "").strip()
    m = re.search(r"/embed/([A-Za-z0-9_-]{6,})", u)
    if m:
        return f"https://www.youtube.com/watch?v={m.group(1)}"
    m = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{6,})", u)
    return f"https://www.youtube.com/watch?v={m.group(1)}" if m else None


def _video_from_node(node) -> str | None:
    try:
        vid = (node.get_attribute("data-yt-init") or "").strip()
        if vid and _YT_ID.fullmatch(vid):
            return f"https://www.youtube.com/watch?v={vid}"
    except Exception:
        pass
    try:
        iframe = node.find_element(
            By.CSS_SELECTOR,
            "iframe[src*='youtube.com/embed'],iframe[src*='youtube-nocookie.com/embed']",
        )
        return _youtube_watch(iframe.get_attribute("src") or "")
    except Exception:
        pass
    try:
        img = node.find_element(By.CSS_SELECTOR, "img[src*='img.youtube.com/vi/']")
        m = re.search(r"img\.youtube\.com/vi/([^/]+)/", img.get_attribute("src") or "")
        if m:
            return f"https://www.youtube.com/watch?v={m.group(1)}"
    except Exception:
        pass
    return None


def _sections_with_videos(driver: webdriver.Chrome) -> list[dict]:
    article = None
    for sel in WRAPPER_SELECTORS:
        hits = driver.find_elements(By.CSS_SELECTOR, sel)
        if hits:
            article = hits[0]
            break
    if article is None:
        return []

    nodes = article.find_elements(
        By.XPATH,
        ".//*[(self::h1 or self::h2 or self::h3 or self::h4 or self::p or self::ol or self::ul or "
        "(self::div and contains(@class,'yt-video')))]",
    )
    sections: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current is None:
            return
        current["text"] = re.sub(r"\s+\n", "\n", current["text"]).strip()
        if not current["heading"] and current["text"]:
            current["heading"] = "Introduction"
        if current["heading"] or current["text"] or current["video"]:
            sections.append(current)
        current = None

    for node in nodes:
        tag = node.tag_name.lower()
        if tag in ("h2", "h3", "h4"):
            flush()
            current = {"heading": (node.text or "").strip(), "text": "", "video": None}
            continue
        if current is None:
            current = {"heading": None, "text": "", "video": None}
        if tag == "p":
            t = (node.text or "").strip()
            if t:
                current["text"] += (("\n" if current["text"] else "") + t)
        elif tag in ("ol", "ul"):
            items = [li.text.strip() for li in node.find_elements(By.TAG_NAME, "li") if li.text.strip()]
            for i, it in enumerate(items, 1):
                bullet = f"{i}. {it}" if tag == "ol" else f"• {it}"
                current["text"] += (("\n" if current["text"] else "") + bullet)
        elif tag == "div" and current.get("video") is None:
            cls = node.get_attribute("class") or ""
            if "yt-video" in cls or node.find_elements(By.CSS_SELECTOR, "div.yt-video"):
                url = _video_from_node(node)
                if url:
                    current["video"] = url
    flush()
    return sections


def extract_article(driver: webdriver.Chrome, url: str) -> dict | None:
    if not _safe_get(driver, url):
        return None
    browser.dismiss_overlays(driver)
    _human_pause(0.5, 0.9)
    try:
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        _human_pause(0.3, 0.6)
        driver.execute_script("window.scrollTo(0, 0);")
    except Exception:
        pass

    title = ""
    for sel in TITLE_SELECTORS:
        try:
            el = driver.find_element(By.CSS_SELECTOR, sel)
            if el.text.strip():
                title = el.text.strip()
                break
        except Exception:
            continue

    sections = _sections_with_videos(driver)
    if not title and not sections:
        return None
    return {"url": url, "title": title, "sections": sections}


def _index_page_url(page: int) -> str:
    """PartSelect blog index uses ?start=N (not ?page=)."""
    if page <= 1:
        return BLOG_INDEX
    return f"{BLOG_INDEX}?start={page}"


def discover_blog_links(driver: webdriver.Chrome, max_pages: int = 19) -> list[tuple[str, str]]:
    found: dict[str, str] = {}
    for page in range(1, max_pages + 1):
        url = _index_page_url(page)
        if not _safe_get(driver, url):
            continue
        for anchor in driver.find_elements(By.CSS_SELECTOR, "a[href*='/blog/']"):
            href = (anchor.get_attribute("href") or "").strip()
            if not href or "/content/blog" in href:
                continue
            if not href.startswith("http"):
                href = urljoin(SITE, href)
            title = (anchor.get_attribute("title") or anchor.text or "").strip()
            title = re.sub(r"\s+", " ", title.split("\n")[0])[:200]
            if href not in found:
                found[href] = title or href
        _human_pause(0.2, 0.5)
    return [(t, u) for u, t in found.items()]


def filter_by_keywords(links: list[tuple[str, str]]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for title, url in links:
        blob = f"{title} {url}".lower()
        if any(kw in blob for kw in TOPIC_KEYWORDS):
            out.append((title, url))
    return out


def save_link_csv(rows: list[tuple[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["title", "url"])
        for title, url in rows:
            writer.writerow([title, url])


def run_articles(
    driver: webdriver.Chrome,
    *,
    max_index_pages: int = 19,
    limit: int | None = None,
    links_csv: Path | None = None,
    output_jsonl: Path | None = None,
) -> int:
    io_utils.ensure_dirs()
    links_csv = links_csv or io_utils.ARTICLE_LINKS_CSV
    output_jsonl = output_jsonl or io_utils.ARTICLE_WORK / "articles_raw.jsonl"

    if links_csv.exists():
        pairs: list[tuple[str, str]] = []
        with links_csv.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                pairs.append((row.get("title") or "", row.get("url") or ""))
    else:
        all_links = discover_blog_links(driver, max_pages=max_index_pages)
        pairs = filter_by_keywords(all_links)
        save_link_csv(pairs, links_csv)

    done = {r.get("url") for r in io_utils.iter_jsonl(output_jsonl)}
    count = 0
    with output_jsonl.open("a", encoding="utf-8") as out_f:
        for i, (_, url) in enumerate(pairs, 1):
            if limit and count >= limit:
                break
            if not url or url in done:
                continue
            doc = extract_article(driver, url)
            if doc:
                out_f.write(json.dumps(doc, ensure_ascii=False) + "\n")
                out_f.flush()
                count += 1
            _human_pause(0.2, 0.4)
    return count
