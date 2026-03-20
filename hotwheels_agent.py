"""
Hot Wheels Drop Alert Agent — GitHub Actions edition
Runs once per invocation (no infinite loop). The cache is a JSON file
committed back to the repo by the workflow so it persists between runs.

Run locally:   python hotwheels_agent.py
Run on CI:     triggered automatically by .github/workflows/poll.yml
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
# Store secrets in GitHub repo → Settings → Secrets and variables → Actions.
# For local runs, export them in your shell or use a .env file.

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")
SEARCH_TERM        = os.environ.get("SEARCH_TERM", "hot wheels")

# Cache file — committed back to the repo by the workflow.
CACHE_FILE = Path("known_listings.json")

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
        log.warning("Telegram credentials not set — skipping send.")
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


def format_alert(platform: str, name: str, price: str, location: str, url: str = "") -> str:
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
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Mobile Safari/537.36"
    )
})

# ─── SCRAPERS ─────────────────────────────────────────────────────────────────

def scrape_blinkit(loc: dict) -> list[dict]:
    listings = []
    try:
        r = SESSION.get(
            "https://blinkit.com/v6/search/products",
            headers={
                "app_client": "consumer",
                "app_version": "1000000",
                "lat": str(loc["lat"]),
                "lon": str(loc["lng"]),
                "device_id": "hotwheels-agent",
                "web_app_version": "1000000",
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


def scrape_zepto(loc: dict) -> list[dict]:
    listings = []
    store_id = loc.get("zepto_store_id", "")
    if not store_id:
        log.info(f"  Zepto [{loc['name']}]: no store_id configured, skipping")
        return listings
    try:
        r = SESSION.post(
            "https://api.zepto.co.in/search/query",
            json={
                "query": SEARCH_TERM,
                "pageNumber": 0,
                "mode": "AUTOSUGGEST",
                "storeId": store_id,
                "latitude": loc["lat"],
                "longitude": loc["lng"],
            },
            timeout=15,
        )
        r.raise_for_status()
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


def scrape_bigbasket(loc: dict) -> list[dict]:
    listings = []
    try:
        r = SESSION.get(
            "https://www.bigbasket.com/product/get-products/",
            headers={"Accept": "application/json", "x-channel": "web"},
            params={"q": SEARCH_TERM, "tab": "product"},
            timeout=15,
        )
        r.raise_for_status()
        for tab in r.json().get("tab_detail", []):
            for p in tab.get("product_map", []):
                prod = p.get("product", {})
                name = prod.get("desc", "")
                pid  = str(prod.get("id", ""))
                slug = prod.get("u", "")
                if "hot wheel" in name.lower() or "hotwheels" in name.lower():
                    listings.append({
                        "id":       make_id("BigBasket", pid, loc["name"]),
                        "platform": "BigBasket",
                        "location": loc["name"],
                        "name":     name,
                        "price":    f"₹{prod.get('sp', '?')}",
                        "url":      f"https://www.bigbasket.com{slug}" if slug else "",
                    })
        log.info(f"  BigBasket [{loc['name']}]: {len(listings)} found")
    except Exception as e:
        log.warning(f"  BigBasket [{loc['name']}] failed: {e}")
    return listings


def scrape_swiggy(loc: dict) -> list[dict]:
    listings = []
    store_id = loc.get("swiggy_store_id", "")
    if not store_id:
        log.info(f"  Swiggy [{loc['name']}]: no store_id configured, skipping")
        return listings
    try:
        r = SESSION.get(
            "https://www.swiggy.com/api/instamart/search",
            headers={"Content-Type": "application/json"},
            params={"query": SEARCH_TERM, "storeId": store_id,
                    "lat": loc["lat"], "lng": loc["lng"]},
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
    log.info(f"══════ Done — {new_count} new listing(s) alerted ══════")


if __name__ == "__main__":
    main()
