"""
Hot Wheels Drop Alert Agent — GitHub Actions edition
Runs once per invocation. Cache is committed back to repo after each run.
"""

import json
import os
import time
import logging
import hashlib
import requests
from pathlib import Path
from datetime import datetime

# ─── LOCATIONS ────────────────────────────────────────────────────────────────

LOCATIONS = [
    {
        "name":  "Koramangala",
        "lat":   12.9352,
        "lng":   77.6245,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_KORAMANGALA", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_KORAMANGALA", ""),
    },
    {
        "name":  "Indiranagar",
        "lat":   12.9784,
        "lng":   77.6408,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_INDIRANAGAR", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_INDIRANAGAR", ""),
    },
    {
        "name":  "Whitefield",
        "lat":   12.9698,
        "lng":   77.7500,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_WHITEFIELD", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_WHITEFIELD", ""),
    },
    {
        "name":  "JP Nagar",
        "lat":   12.9102,
        "lng":   77.5841,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_JPNAGAR", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_JPNAGAR", ""),
    },
    {
        "name":  "Hebbal",
        "lat":   13.0353,
        "lng":   77.5950,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_HEBBAL", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_HEBBAL", ""),
    },
    {
        "name":  "Electronic City",
        "lat":   12.8399,
        "lng":   77.6770,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_ECITY", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_ECITY", ""),
    },
    {
        "name":  "Malleshwaram",
        "lat":   13.0027,
        "lng":   77.5705,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_MALLESHWARAM", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_MALLESHWARAM", ""),
    },
    {
        "name":  "HSR Layout",
        "lat":   12.9116,
        "lng":   77.6473,
        "zepto_store_id":  os.environ.get("ZEPTO_STORE_HSR", ""),
        "swiggy_store_id": os.environ.get("SWIGGY_STORE_HSR", ""),
    },
]

# ─── CONFIG ───────────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
SEARCH_TERM        = os.environ.get("SEARCH_TERM", "hot wheels")
CACHE_FILE         = Path("known_listings.json")

# ─── LOGGING ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ─── CACHE ────────────────────────────────────────────────────────────────────

def load_cache() -> set:
    if CACHE_FILE.exists():
        return set(json.loads(CACHE_FILE.read_text()).get("seen_ids", []))
    return set()

def save_cache(seen_ids: set):
    CACHE_FILE.write_text(json.dumps({"seen_ids": sorted(seen_ids)}, indent=2))

def make_id(platform: str, product_id: str, location: str) -> str:
    return hashlib.md5(f"{platform}:{product_id}:{location}".encode()).hexdigest()

# ─── TELEGRAM ─────────────────────────────────────────────────────────────────

def send_telegram(message: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not set — skipping.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": message,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=10,
        )
        r.raise_for_status()
        log.info("Telegram message sent.")
    except Exception as e:
        log.error(f"Telegram send failed: {e}")

def format_alert(platform, name, price, location, url=""):
    ts = datetime.now().strftime("%d %b %Y, %I:%M %p")
    lines = [
        "🚗 <b>New Hot Wheels Drop!</b>",
        f"📦 <b>Platform:</b> {platform}",
        f"📍 <b>Location:</b> {location}, Bengaluru",
        f"🏷️ <b>Name:</b> {name}",
        f"💰 <b>Price:</b> {price}",
    ]
    if url:
        lines.append(f"🔗 <a href='{url}'>View listing</a>")
    lines.append(f"🕐 {ts}")
    return "\n".join(lines)

# ─── HTTP SESSION ─────────────────────────────────────────────────────────────

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Pixel 8) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Mobile Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-IN,en;q=0.9,hi;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "sec-ch-ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    "sec-ch-ua-mobile": "?1",
    "sec-ch-ua-platform": '"Android"',
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
})

# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def scrape_blinkit(loc):
    listings = []
    try:
        SESSION.get("https://blinkit.com/", timeout=15)
        time.sleep(1)
        r = SESSION.get(
            "https://blinkit.com/v6/search/products",
            headers={
                "app_client":      "consumer",
                "app_version":     "1000000",
                "lat":             str(loc["lat"]),
                "lon":             str(loc["lng"]),
                "device_id":       "hotwheels-agent",
                "web_app_version": "1000000",
                "Referer":         "https://blinkit.com/",
                "Origin":          "https://blinkit.com",
            },
            params={"search_type": "AutoComplete", "query": SEARCH_TERM},
            timeout=15,
        )
        r.raise_for_status()
        for p in r.json().get("objects", []):
            name = p.get("name", "")
            pid  = str(p.get("id", ""))
            if "hot wheel" in name.lower() or "hotwheels" in name.lower():
                listings.append({
                    "id":       make_id("Blinkit", pid, loc["name"]),
                    "platform": "Blinkit",
                    "location": loc["name"],
                    "name":     name,
                    "price":    f"₹{p.get('price', '?')}",
                    "url":      f"https://blinkit.com/prn/{p.get('product_slug','')}/prid/{pid}/",
                })
        log.info(f"  Blinkit [{loc['name']}]: {len(listings)} found")
    except Exception as e:
        log.warning(f"  Blinkit [{loc['name']}] failed: {e}")
    return listings


def scrape_zepto(loc):
    listings = []
    store_id = loc.get("zepto_store_id", "")
    if not store_id:
        log.info(f"  Zepto [{loc['name']}]: no store_id configured, skipping")
        return listings
    try:
        endpoints = [
            "https://api.zepto.co.in/search/query",
            "https://api.zeptonow.com/api/v3/search",
        ]
        r = None
        for endpoint in endpoints:
            try:
                r = SESSION.post(
                    endpoint,
                    json={
                        "query":      SEARCH_TERM,
                        "pageNumber": 0,
                        "mode":       "AUTOSUGGEST",
                        "storeId":    store_id,
                        "latitude":   loc["lat"],
                        "longitude":  loc["lng"],
                    },
                    headers={
                        "Referer": "https://www.zepto.com/",
                        "Origin":  "https://www.zepto.com",
                    },
                    timeout=15,
                )
                if r.status_code == 200:
                    break
            except Exception:
                continue

        if not r or r.status_code != 200:
            log.warning(f"  Zepto [{loc['name']}]: all endpoints failed")
            return listings

        for section in r.json().get("data", {}).get("sections", []):
            for p in section.get("layout", []):
                pr   = p.get("productResponse", {})
                name = pr.get("name", "")
                pid  = str(pr.get("productId", ""))
                if "hot wheel" in name.lower() or "hotwheels" in name.lower():
                    listings.append({
                        "id":       make_id("Zepto", pid, loc["name"]),
                        "platform": "Zepto",
                        "location": loc["name"],
                        "name":     name,
                        "price":    f"₹{pr.get('discountedPrice', '?')}",
                        "url":      "",
                    })
        log.info(f"  Zepto [{loc['name']}]: {len(listings)} found")
    except Exception as e:
        log.warning(f"  Zepto [{loc['name']}] failed: {e}")
    return listings


def scrape_bigbasket(loc):
    """
    Scrapes the Hot Wheels brand page on BigBasket directly.
    Only runs for Koramangala since BigBasket is city-wide, not per dark store.
    """
    import re as _re
    if loc["name"] != "Koramangala":
        return []

    listings = []
    page = 1

    try:
        while True:
            url = f"https://www.bigbasket.com/pb/hot-wheels/?page={page}"
            r = SESSION.get(
                url,
                headers={
                    "Accept":  "text/html,application/xhtml+xml,*/*;q=0.9",
                    "Referer": "https://www.bigbasket.com/",
                },
                timeout=15,
            )
            r.raise_for_status()

            matches = _re.findall(r'/pd/(\d+)/([^/\"]+)/', r.text)
            if not matches:
                break

            seen_on_page = set()
            for pid, slug in matches:
                if pid in seen_on_page:
                    continue
                seen_on_page.add(pid)

                name = slug.replace("-", " ").title()
                name = _re.sub(r"\s+\d+\s+(Pc|Pcs|Set|Pack).*$", "", name, flags=_re.IGNORECASE).strip()

                price_match = _re.search(
                    rf"/pd/{pid}/[^\"]+.*?\u20b9(\d+)",
                    r.text, _re.DOTALL
                )
                price = f"₹{price_match.group(1)}" if price_match else "₹?"

                listings.append({
                    "id":       make_id("BigBasket", pid, loc["name"]),
                    "platform": "BigBasket",
                    "location": loc["name"],
                    "name":     name,
                    "price":    price,
                    "url":      f"https://www.bigbasket.com/pd/{pid}/{slug}/",
                })

            if 'page=' not in r.text or page >= 5:
                break
            page += 1

        log.info(f"  BigBasket: {len(listings)} Hot Wheels listings found")
    except Exception as e:
        log.warning(f"  BigBasket failed: {e}")
    return listings


def scrape_swiggy(loc):
    listings = []
    store_id = loc.get("swiggy_store_id", "")
    if not store_id:
        log.info(f"  Swiggy [{loc['name']}]: no store_id configured, skipping")
        return listings
    try:
        SESSION.get("https://www.swiggy.com/instamart", timeout=15)
        time.sleep(1)
        r = SESSION.get(
            "https://www.swiggy.com/api/instamart/search",
            headers={
                "Referer": "https://www.swiggy.com/instamart",
                "Origin":  "https://www.swiggy.com",
            },
            params={
                "query":   SEARCH_TERM,
                "storeId": store_id,
                "lat":     loc["lat"],
                "lng":     loc["lng"],
            },
            timeout=15,
        )
        r.raise_for_status()
        for section in r.json().get("data", {}).get("sections", []):
            for widget in section.get("widget_container", {}).get("widgets", []):
                for p in widget.get("data", {}).get("items", []):
                    name = p.get("display", {}).get("name", "")
                    pid  = str(p.get("id", ""))
                    if "hot wheel" in name.lower() or "hotwheels" in name.lower():
                        listings.append({
                            "id":       make_id("Swiggy", pid, loc["name"]),
                            "platform": "Swiggy Instamart",
                            "location": loc["name"],
                            "name":     name,
                            "price":    f"₹{p.get('display',{}).get('default_price','?')}",
                            "url":      "",
                        })
        log.info(f"  Swiggy [{loc['name']}]: {len(listings)} found")
    except Exception as e:
        log.warning(f"  Swiggy [{loc['name']}] failed: {e}")
    return listings

# ─── MAIN ─────────────────────────────────────────────────────────────────────

SCRAPERS = [scrape_blinkit, scrape_zepto, scrape_bigbasket, scrape_swiggy]


def main():
    log.info("══════ Hot Wheels check starting ══════")
    seen      = load_cache()
    new_count = 0

    for loc in LOCATIONS:
        log.info(f"── {loc['name']} ──")
        for scraper in SCRAPERS:
            for item in scraper(loc):
                if item["id"] not in seen:
                    seen.add(item["id"])
                    new_count += 1
                    send_telegram(format_alert(
                        platform=item["platform"],
                        name=item["name"],
                        price=item["price"],
                        location=item["location"],
                        url=item.get("url", ""),
                    ))
                    log.info(f"  ✓ Alert: [{item['platform']} / {item['location']}] {item['name']}")
                    time.sleep(1)

    save_cache(seen)

    # Daily heartbeat at 9am so you know the agent is alive
    if new_count == 0 and datetime.now().hour == 9 and datetime.now().minute < 30:
        send_telegram("🤖 Hot Wheels agent is running fine — no new drops yet today.")

    log.info(f"══════ Done — {new_count} new listing(s) alerted ══════")


if __name__ == "__main__":
    main()
