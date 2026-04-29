"""
Crawl báo cáo thị trường Halal từ World Halal Forum, MIHAS, VCCI.
Chỉ lấy nội dung liên quan đến báo cáo thị trường Halal toàn cầu.

Cache 2 tầng (file-based, survive restart):
  L1: LLM summary — TTL 6 giờ  → 0 crawl + 0 LLM token
  L2: Raw context  — TTL 2 giờ  → 0 crawl, chỉ tốn LLM token
"""

import json
import logging
import time
from pathlib import Path
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

# ── Cache config ───────────────────────────────────────────────────────────────
_CACHE_DIR = Path(__file__).parent.parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
_CACHE_RAW = _CACHE_DIR / "halal_news_raw.json"  # L2: raw crawled content
_CACHE_SUM = _CACHE_DIR / "halal_news_sum.json"  # L1: LLM summary
_TTL_RAW = 2 * 3600  # 2 giờ
_TTL_SUM = 6 * 3600  # 6 giờ


def _cache_read(path: Path, ttl: int):
    """Đọc cache nếu còn hạn, trả về None nếu hết hạn hoặc không có."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - data["ts"] < ttl:
            return data["value"]
    except Exception:
        pass
    return None


def _cache_write(path: Path, value: str):
    """Ghi giá trị vào cache file."""
    try:
        path.write_text(json.dumps({"ts": time.time(), "value": value}, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning(f"Cache write error: {e}")


def get_cached_summary(lang: str = "vi") -> str | None:
    """L1: Lấy LLM summary đã cache (6 giờ), theo ngôn ngữ."""
    path = _CACHE_DIR / f"halal_news_sum_{lang}.json"
    return _cache_read(path, _TTL_SUM)


def get_cached_raw() -> str | None:
    """L2: Lấy raw crawled content đã cache (2 giờ)."""
    return _cache_read(_CACHE_RAW, _TTL_RAW)


def save_cached_raw(content: str):
    _cache_write(_CACHE_RAW, content)


def save_cached_summary(summary: str, lang: str = "vi"):
    path = _CACHE_DIR / f"halal_news_sum_{lang}.json"
    _cache_write(path, summary)


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

_GREETING_PATTERNS = [
    "assalamu alaikum",
    "assalamualaikum",
    "as-salamu alaykum",
    "assalamu'alaikum",
    "assalam alaikum",
    "السلام عليكم",
    "salam alaikum",
    "salamualaikum",
    "wa alaikum",
    "waалайкум",
    "bismillah",
    "alhamdulillah",
    "subhanallah",
    "dear brothers",
    "dear sisters",
    "dear brother",
    "dear sister",
    "beloved brothers",
    "beloved sisters",
]


def _strip_greetings(text: str) -> str:
    """Xoá các dòng chứa câu chào hỏi Islamic ra khỏi nội dung crawl."""
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line_lower = line.lower().strip()
        if any(pat in line_lower for pat in _GREETING_PATTERNS):
            continue
        cleaned.append(line)
    return "\n".join(cleaned).strip()


# Từ khoá tin tức/thị trường — cần có ít nhất 1
_NEWS_KEYWORDS = [
    # Vietnamese
    "tin tức",
    "tình hình",
    "thị trường",
    "cập nhật",
    "mới nhất",
    "kinh tế",
    "xu hướng",
    "báo cáo",
    "diễn đàn",
    "tin ",
    # English
    "news",
    "market",
    "update",
    "latest",
    "trend",
    "report",
    "forum",
    "industry",
    # Malay
    "berita",
    "pasaran",
    "terkini",
    "perkembangan",
    "industri",
    "laporan",
    # Arabic
    "أخبار",
    "سوق",
    "تقرير",
    "صناعة",
    "اتجاه",
    "تطور",
]

# Từ khoá Halal — cần có ít nhất 1
_HALAL_KEYWORDS = ["halal", "hồi giáo", "muslim", "islam", "حلال"]


def is_halal_news_query(text: str) -> bool:
    t = text.lower().strip()
    has_news = any(kw in t for kw in _NEWS_KEYWORDS)
    has_halal = any(kw in t for kw in _HALAL_KEYWORDS)
    return has_news and has_halal


# Từ khoá để lọc đoạn văn có liên quan đến báo cáo thị trường Halal
_MARKET_RELEVANCE_KEYWORDS = [
    "halal market",
    "halal industry",
    "halal economy",
    "halal sector",
    "halal food",
    "halal trade",
    "halal export",
    "halal certification",
    "halal report",
    "halal growth",
    "halal billion",
    "halal trillion",
    "thị trường halal",
    "kinh tế halal",
    "xuất khẩu halal",
    "ngành halal",
    "chứng nhận halal",
    "tăng trưởng halal",
    "muslim consumer",
    "islamic economy",
    "global halal",
    "southeast asia halal",
    "asean halal",
]

# Query cụ thể nhắm vào báo cáo thị trường — không lấy nội dung tùy tiện
_HALAL_FORUM_SOURCES = [
    # World Halal Forum — báo cáo và tóm tắt sự kiện
    '"world halal forum" halal market report 2024 OR 2025',
    'worldhalalforum.org "halal market" OR "halal industry" 2025',
    # MIHAS — Malaysia International Halal Showcase
    'MIHAS 2024 OR 2025 "halal market" OR "halal industry" report',
    'site:mihas.com.my "halal" market report OR statistics',
    # VCCI — Liên đoàn Thương mại và Công nghiệp Việt Nam
    'site:vcci.com.vn "halal" thị trường báo cáo 2024 OR 2025',
    'VCCI halal "thị trường" OR "xuất khẩu" Việt Nam 2025',
]


def _is_relevant_paragraph(text: str) -> bool:
    """Kiểm tra đoạn văn có chứa thông tin về thị trường Halal không."""
    t = text.lower()
    return any(kw in t for kw in _MARKET_RELEVANCE_KEYWORDS)


def _fetch_halal_report_text(url: str, timeout: int = 8) -> str:
    """
    Fetch bài báo và chỉ giữ lại các đoạn văn liên quan đến báo cáo thị trường Halal.
    """
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe", "noscript"]):
            tag.decompose()

        # Lấy toàn bộ các đoạn văn (p tag)
        paragraphs = soup.find_all("p")
        if not paragraphs:
            # Fallback: lấy từ main content area
            for selector in ["article", "main", ".article-body", ".content"]:
                el = soup.select_one(selector)
                if el:
                    text = el.get_text(separator="\n", strip=True)
                    # Lọc từng dòng
                    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 40]
                    relevant = [l for l in lines if _is_relevant_paragraph(l)]
                    if relevant:
                        return "\n".join(relevant[:15])
                    # Nếu không lọc được, lấy 300 từ đầu
                    words = text.split()
                    return " ".join(words[:300])
            return ""

        # Chỉ giữ các đoạn văn liên quan đến Halal market
        relevant_paragraphs = []
        for p in paragraphs:
            text = p.get_text(strip=True)
            if len(text) > 40 and _is_relevant_paragraph(text):
                relevant_paragraphs.append(text)

        if not relevant_paragraphs:
            # Không lọc được — lấy snippet từ search result thay thế
            return ""

        # Giới hạn 400 từ
        combined = " ".join(relevant_paragraphs)
        words = combined.split()
        return _strip_greetings(" ".join(words[:400]))

    except Exception as e:
        log.warning(f"Failed to fetch {url}: {e}")
        return ""


def crawl_halal_news() -> str:
    """
    Tìm kiếm và trả về chỉ các nội dung báo cáo thị trường Halal
    từ World Halal Forum, MIHAS, VCCI.
    Kiểm tra L2 cache trước khi crawl thật.
    """
    # L2 cache: raw content còn hạn → bỏ qua crawl
    cached_raw = get_cached_raw()
    if cached_raw:
        log.info("Halal news: L2 cache hit (raw content)")
        return cached_raw

    try:
        from ddgs import DDGS
    except ImportError:
        return "[Không thể crawl: thư viện ddgs chưa được cài đặt]"

    all_results = []
    seen_urls = set()
    ddgs = DDGS()

    for query in _HALAL_FORUM_SOURCES:
        try:
            results = ddgs.text(query, max_results=2)
            for r in results:
                url = r.get("href", "")
                title = r.get("title", "")
                snippet = r.get("body", "")
                # Bỏ qua kết quả không liên quan đến Halal market
                if not _is_relevant_paragraph(title + " " + snippet):
                    log.info(f"Skipped (not relevant): {title[:60]}")
                    continue
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                        }
                    )
        except Exception as e:
            log.warning(f"Search error for '{query}': {e}")

    if not all_results:
        return "[Không tìm được báo cáo thị trường Halal từ các nguồn ưu tiên]"

    # Fetch và lọc nội dung (tối đa 5 bài)
    context_blocks = []
    for i, item in enumerate(all_results[:5], 1):
        article_text = _fetch_halal_report_text(item["url"])
        if not article_text:
            # Fallback: dùng snippet nếu snippet liên quan
            if _is_relevant_paragraph(item["snippet"]):
                article_text = item["snippet"]

        if article_text:
            article_text = _strip_greetings(article_text)
            source_label = ""
            url_lower = item["url"].lower()
            if "worldhalalforum" in url_lower:
                source_label = "[World Halal Forum]"
            elif "mihas" in url_lower:
                source_label = "[MIHAS]"
            elif "vcci" in url_lower:
                source_label = "[VCCI]"

            block = f"{source_label} {item['title']}\n{article_text}"
            context_blocks.append(block)

    if not context_blocks:
        return "[Không truy cập được nội dung báo cáo thị trường Halal]"

    result = "\n\n---\n\n".join(context_blocks)
    save_cached_raw(result)
    log.info("Halal news: raw content cached (L2)")
    return result
