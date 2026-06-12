"""
搜尋引擎：Scrapling StealthyFetcher 搜 Google，requests 驗證 page.line.me
"""
import re
import asyncio
import requests
from typing import AsyncGenerator

try:
    from scrapling.fetchers import StealthyFetcher
    SCRAPLING_OK = True
except ImportError:
    SCRAPLING_OK = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# 各縣市的搜尋關鍵字（補足子城市以提高覆蓋率），由北到南排列
COUNTY_SEARCH_TERMS = {
    "基隆市": ["基隆", "七堵", "暖暖"],
    "台北市": ["台北", "信義區", "大安區", "中山區", "內湖", "士林", "松山", "萬華"],
    "新北市": ["新北", "板橋", "中和", "永和", "三重", "新莊", "新店", "土城", "蘆洲", "汐止"],
    "桃園市": ["桃園", "中壢", "平鎮", "八德", "龜山", "楊梅", "蘆竹"],
    "新竹市": ["新竹市", "東區新竹", "竹科"],
    "新竹縣": ["竹北", "新竹縣", "湖口", "竹東", "新豐", "關西"],
    "苗栗縣": ["苗栗", "頭份", "竹南", "通霄", "苑裡"],
    "台中市": ["台中", "北屯", "西屯", "南屯", "霧峰", "烏日", "大里", "太平"],
    "彰化縣": ["彰化", "員林", "鹿港", "和美", "溪湖", "北斗"],
    "南投縣": ["南投", "草屯", "埔里", "竹山", "集集"],
    "雲林縣": ["雲林", "斗六", "虎尾", "西螺", "北港", "麥寮"],
    "嘉義縣": ["嘉義縣", "朴子", "太保", "義竹", "布袋"],
    "嘉義市": ["嘉義市"],
    "台南市": ["台南", "永康", "新營", "歸仁", "仁德", "安南", "東區台南", "中西台南"],
    "高雄市": ["高雄", "三民", "左營", "鳳山", "前鎮", "苓雅", "楠梓", "鼓山", "岡山"],
    "屏東縣": ["屏東", "潮州", "東港", "內埔", "恆春"],
    "宜蘭縣": ["宜蘭", "羅東", "礁溪", "蘇澳", "頭城"],
    "花蓮縣": ["花蓮", "吉安", "玉里"],
    "台東縣": ["台東", "成功台東", "關山"],
    "澎湖縣": ["澎湖", "馬公"],
    "金門縣": ["金門", "金城金門"],
    "連江縣": ["連江", "馬祖", "南竿"],
}

# 縣市名稱用於地址比對，由北到南排列
COUNTY_ADDR_KEYWORDS = {
    "基隆市": ["基隆市"],
    "台北市": ["台北市", "臺北市"],
    "新北市": ["新北市"],
    "桃園市": ["桃園市"],
    "新竹市": ["新竹市"],
    "新竹縣": ["新竹縣"],
    "苗栗縣": ["苗栗縣", "苗栗市", "頭份市", "竹南鎮", "通霄鎮", "苑裡鎮", "後龍鎮"],
    "台中市": ["台中市", "臺中市"],
    "彰化縣": ["彰化縣", "彰化市", "員林市", "鹿港鎮", "和美鎮", "溪湖鎮"],
    "南投縣": ["南投縣", "南投市", "草屯鎮", "埔里鎮", "竹山鎮", "集集鎮"],
    "雲林縣": ["雲林縣", "斗六市", "虎尾鎮", "西螺鎮", "北港鎮", "麥寮鄉"],
    "嘉義縣": ["嘉義縣"],
    "嘉義市": ["嘉義市"],
    "台南市": ["台南市", "臺南市"],
    "高雄市": ["高雄市"],
    "屏東縣": ["屏東縣"],
    "宜蘭縣": ["宜蘭縣"],
    "花蓮縣": ["花蓮縣"],
    "台東縣": ["台東縣", "臺東縣"],
    "澎湖縣": ["澎湖縣"],
    "金門縣": ["金門縣"],
    "連江縣": ["連江縣"],
}

MAX_GOOGLE_PAGES = 3   # 每個搜尋詞翻幾頁
SEARCH_DELAY    = 1.5  # Google 請求間隔（秒）


def clean_line_url(href: str) -> str | None:
    """從各種格式的 href 提取乾淨的 page.line.me URL"""
    # Google redirect format
    if "/url?q=" in href:
        m = re.search(r"/url\?q=(https://page\.line\.me/[^&]+)", href)
        if m:
            href = m.group(1)

    if "page.line.me" not in href:
        return None

    # 移除 sub-paths (showcase / media / signboard / profile / img)
    href = re.sub(r"/(showcase|media|signboard|profile|img)(/.*)?" , "", href)
    href = href.split("?")[0].rstrip("/")

    # 排除過短或明顯無效的 URL
    path = href.split("page.line.me/")[-1]
    if not path or path in ("", "/"):
        return None

    return href


async def google_search_line_urls(industry: str, area: str, page: int) -> list[dict]:
    """用 Scrapling StealthyFetcher 搜 Google，回傳 page.line.me URL 清單"""
    query = f"{area} {industry} site:page.line.me"
    url = f"https://www.google.com/search?q={query}&num=20&hl=zh-TW&start={page * 10}"

    if not SCRAPLING_OK:
        return []

    try:
        result = await StealthyFetcher.async_fetch(
            url, headless=True, network_idle=True, timeout=30000
        )

        seen = set()
        urls = []

        for link in result.css("a[href]"):
            href = link.attrib.get("href", "") if hasattr(link, "attrib") else ""
            clean = clean_line_url(href)
            if clean and clean not in seen:
                seen.add(clean)
                try:
                    desc = (link.parent.text if link.parent else link.text or "")[:120]
                except Exception:
                    desc = ""
                urls.append({"url": clean, "desc": desc.replace("\n", " ").strip()})

        return urls

    except Exception as e:
        return []


def verify_line_page(url: str, target_counties: list[str], excludes: list[str]) -> dict | None:
    """抓取 page.line.me 頁面，確認地址在目標縣市且非排除類型"""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            return None

        html = resp.text

        # 名稱
        m = re.search(r"<title>([^<|]+)", html)
        name = m.group(1).strip() if m else ""
        name = re.sub(r"\s*\|\s*LINE.*", "", name).strip()
        if not name:
            return None

        # 排除關鍵字
        combined = name + html[:3000]
        for kw in excludes:
            if kw and kw in combined:
                return None

        # 純文字
        body = re.sub(r"<[^>]+>", " ", html)
        body = re.sub(r"\s+", " ", body)[:2000]

        # 找地址（比對縣市關鍵字，優先抓到門牌號為止，避免夾雜雜訊）
        found_county = None
        address = ""
        for county in target_counties:
            for kw in COUNTY_ADDR_KEYWORDS.get(county, [county]):
                # 優先：縣市 → … → 號（可含樓層／之N）的完整門牌
                m2 = re.search(
                    rf"({re.escape(kw)}[^\n<>\"，。;；,a-zA-Z]{{2,40}}?號(?:\d+樓)?(?:之\d+)?)",
                    body,
                )
                if not m2:
                    # 退回：抓一段後再砍掉尾巴雜訊
                    m2 = re.search(rf"({re.escape(kw)}[^\n<>\"，。;；,a-zA-Z]{{2,40}})", body)
                if m2:
                    address = m2.group(1).strip()
                    found_county = county
                    break
            if found_county:
                break

        if not found_county:
            return None

        # 砍掉地址尾巴常見雜訊（電話、英文導覽字等）
        address = re.split(
            r"\s*(?:電話|Tel|TEL|Mixed|In-store|Top|See|LINE|營業|預約|☎|本店)",
            address,
        )[0].strip()
        # 不含路名門牌特徵字的多半是店名碎片誤命中，寧可留空
        if address and not re.search(r"[路街道段號巷弄]", address):
            address = ""

        # 電話（須以 0 開頭，且前後不接其他數字，避免誤抓長數字串）
        m3 = re.search(r"(?<!\d)(0\d{1,2}[\s\-]?\d{3,4}[\s\-]?\d{3,4})(?!\d)", body)
        phone = m3.group(1).strip() if m3 else ""

        # LINE@ ID（排除 JSON-LD 保留字：@context @type @id @graph 等）
        _JSONLD_SKIP = {"context", "type", "id", "graph", "value", "language",
                        "base", "vocab", "container", "direction", "set", "list"}
        url_code = url.rstrip("/").split("/")[-1]
        line_id = f"@{url_code}" if not url_code.startswith("@") else url_code
        for m4 in re.finditer(r'["\s](@[A-Za-z0-9._\-]{3,30})["\s<]', html):
            candidate = m4.group(1)[1:].lower()
            if candidate not in _JSONLD_SKIP:
                line_id = m4.group(1)
                break

        return {
            "county": found_county,
            "name": name,
            "address": address,
            "phone": phone,
            "line_id": line_id,
            "line_url": url,
        }

    except Exception:
        return None


async def run_full_search(
    industry: str,
    counties: list[str],
    excludes: list[str],
) -> AsyncGenerator[dict, None]:
    """主搜尋流程，async generator，逐事件 yield"""

    if not SCRAPLING_OK:
        yield {"type": "error", "message": "Scrapling 未安裝，請執行 pip install scrapling[all] && scrapling install"}
        return

    yield {"type": "status", "message": "🚀 初始化 Scrapling 搜尋引擎..."}
    await asyncio.sleep(0.1)

    all_urls: set[str] = set()
    found_count = 0

    for county in counties:
        search_terms = COUNTY_SEARCH_TERMS.get(county, [county])

        for term in search_terms:
            for page in range(MAX_GOOGLE_PAGES):
                yield {"type": "status", "message": f"🔍 搜尋「{term} {industry}」第 {page+1} 頁..."}

                urls = await google_search_line_urls(industry, term, page)
                new_urls = [u for u in urls if u["url"] not in all_urls]

                if not new_urls and page > 0:
                    break  # 沒有新結果，不用繼續翻頁

                for u in new_urls:
                    all_urls.add(u["url"])
                    short_id = u["url"].split("/")[-1]
                    yield {"type": "status", "message": f"   ✅ 驗證 {short_id}..."}

                    result = await asyncio.to_thread(
                        verify_line_page, u["url"], [county], excludes
                    )

                    if result:
                        found_count += 1
                        yield {"type": "found", "data": result, "total": found_count}
                        yield {
                            "type": "status",
                            "message": f"   ✅ 找到：{result['name']} ({county})",
                        }

                await asyncio.sleep(SEARCH_DELAY)

    yield {"type": "complete", "total": found_count}
