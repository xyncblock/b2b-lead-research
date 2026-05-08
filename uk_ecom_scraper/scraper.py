#!/usr/bin/env python3
"""
UK E-commerce Store Finder
Runs 24/7 — saves every 500 verified stores to a new CSV and sends to Telegram.
"""

import os, sys, csv, time, json, re, random, logging, hashlib, signal
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin, quote_plus
from datetime import datetime
from difflib import SequenceMatcher
from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

# ── Config ───────────────────────────────────────────────────────────────────
BASE_DIR    = "/home/expertfox/.openclaw/workspace/uk_ecom_data"
STATE_FILE  = os.path.join(BASE_DIR, "state.json")
BROKEN_FILE = os.path.join(BASE_DIR, "broken_sites.csv")
LOG_FILE    = os.path.join(BASE_DIR, "scraper.log")
BATCH_SIZE  = 500
TG_TOKEN    = "8706876222:AAFtBgLcbhc5bvJwS8Dy1Ek3-7IgjpjKY-I"
TG_CHAT_ID  = "7777269308"
COMPANIES_HOUSE_KEY = os.getenv("COMPANIES_HOUSE_API_KEY", "")

# Delays (seconds)  — randomised to avoid detection
SEARCH_DELAY = (10, 25)
SITE_DELAY   = (4, 10)
PAGE_TIMEOUT = 20_000   # ms

# ── Fields ───────────────────────────────────────────────────────────────────
FIELDS = [
    "business_name", "owner_name", "email", "phone",
    "website", "industry", "category", "platform",
    "city", "google_location",
    "facebook", "instagram", "twitter", "linkedin", "tiktok",
    "email_verified", "source", "found_at",
]
BROKEN_FIELDS = ["url", "reason", "found_at"]

# ── Platform fingerprints ─────────────────────────────────────────────────────
PLATFORMS = {
    "Shopify":     ["cdn.shopify.com", "myshopify.com", "shopify.com/s/files", "Shopify.theme"],
    "WooCommerce": ["woocommerce", "wc-cart", "wc-block", "wp-content/plugins/woocommerce"],
    "Magento":     ["Mage.", "/pub/static/", "magento", "mage/"],
    "BigCommerce": ["bigcommerce.com", "bc-sf-filter", "bigcommerce"],
    "Squarespace": ["squarespace.com", "sqsp.net", "static1.squarespace"],
    "Wix":         ["wixstatic.com", "wix.com/_api", "X-Wix-"],
    "PrestaShop":  ["prestashop", "presta_", "id_product"],
    "OpenCart":    ["opencart", "route=product/product"],
    "Volusion":    ["volusion.com", "volusion"],
    "3dcart":      ["3dcart.com", "shift4shop.com"],
    "Ecwid":       ["ecwid.com", "app.ecwid"],
    "Weebly":      ["weebly.com", "weeblysite.com"],
    "GoDaddy":     ["secureserver.net", "godaddy.com/stores"],
}

# ── Industries / categories ───────────────────────────────────────────────────
INDUSTRY_KEYWORDS = {
    "Fashion & Clothing":   ["fashion","clothing","apparel","dress","shirt","trouser","jacket","coat","shoes","footwear","boots","handbag","accessories"],
    "Beauty & Cosmetics":   ["beauty","cosmetics","skincare","makeup","hair","nail","perfume","fragrance","serum","moisturiser"],
    "Electronics":          ["electronics","gadget","laptop","phone","camera","tv","audio","headphone","computer","tablet","gaming"],
    "Home & Garden":        ["home","garden","furniture","decor","kitchen","bedding","curtain","lighting","plant","tool","diy"],
    "Food & Drink":         ["food","drink","beverage","wine","beer","coffee","tea","organic","snack","chocolate","gin","whisky"],
    "Health & Wellness":    ["health","wellness","supplement","vitamin","fitness","gym","yoga","nutrition","protein","cbd"],
    "Sports & Outdoor":     ["sport","outdoor","cycling","running","hiking","golf","football","cricket","swimming","climbing"],
    "Toys & Games":         ["toy","game","puzzle","lego","children","kids","baby","infant","nursery"],
    "Books & Media":        ["book","music","film","dvd","vinyl","cd","art","craft","stationery"],
    "Jewellery & Watches":  ["jewellery","jewelry","watch","ring","necklace","bracelet","earring","diamond","gold","silver"],
    "Pet Supplies":         ["pet","dog","cat","bird","fish","hamster","vet","animal"],
    "Automotive":           ["car","automotive","vehicle","tyre","motor","van","bike","motorcycle","parts"],
}

# ── Search queries ────────────────────────────────────────────────────────────
SEARCH_QUERIES = [
    # Generic UK ecommerce
    "UK independent online shop \"add to basket\" \"free delivery\"",
    "site:*.co.uk \"add to cart\" shop",
    "UK online store \"buy now\" checkout clothing",
    "UK online shop \"powered by shopify\"",
    "UK ecommerce \"woocommerce\" shop",
    # Category-specific
    "UK fashion boutique online shop",
    "UK beauty skincare online store",
    "UK electronics gadgets online shop",
    "UK home decor furniture online store",
    "UK food drink online shop delivery",
    "UK health supplements online store",
    "UK sports outdoor online shop",
    "UK toys games children online store",
    "UK jewellery watches online shop",
    "UK pet supplies online store",
    "UK books art craft online shop",
    "UK handmade gifts online store",
    "UK organic natural products online shop",
    "UK vintage retro clothing online",
    "UK luxury goods online store",
    # City-specific
    "London online shop ecommerce",
    "Manchester online store ecommerce",
    "Birmingham UK online shop",
    "Edinburgh Scotland online store",
    "Bristol UK online shop ecommerce",
    "Leeds UK online store",
    "Liverpool UK online shop",
    "Cardiff Wales online store",
    "Glasgow Scotland online shop",
    "Sheffield UK ecommerce store",
    "Brighton UK online shop",
    "Oxford UK online store",
    # Platform-specific
    "\"built with shopify\" UK store",
    "\"powered by bigcommerce\" UK",
    "UK small business online shop \"free returns\"",
    "UK artisan shop online store handmade",
    "UK sustainable eco-friendly online shop",
    "UK plus size clothing online store",
    "UK children baby clothing online shop",
    "UK wedding accessories online store",
    "UK gardening tools plants online shop",
    "UK coffee tea subscription online",
    "UK wine spirits online delivery",
    "UK cycling mountain bike online shop",
    "UK running shoes sports online store",
]

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
]

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ── State ─────────────────────────────────────────────────────────────────────
def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "batch": 1,
        "total_found": 0,
        "batch_count": 0,
        "seen_domains": [],
        "query_index": 0,
        "dir_index": 0,
        "broken_count": 0,
    }

def save_state(s):
    with open(STATE_FILE, "w") as f:
        json.dump(s, f, indent=2)

# ── CSV helpers ───────────────────────────────────────────────────────────────
def csv_path(batch_num):
    return os.path.join(BASE_DIR, f"uk_ecom_{batch_num:04d}.csv")

def ensure_broken_csv():
    if not os.path.exists(BROKEN_FILE):
        with open(BROKEN_FILE, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=BROKEN_FIELDS).writeheader()

def write_broken(url, reason):
    with open(BROKEN_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=BROKEN_FIELDS)
        w.writerow({"url": url, "reason": reason, "found_at": now()})

def ensure_batch_csv(batch_num):
    path = csv_path(batch_num)
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=FIELDS).writeheader()
    return path

def append_store(batch_num, store):
    path = csv_path(batch_num)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        w.writerow(store)

# ── Telegram ──────────────────────────────────────────────────────────────────
def tg_message(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=15,
        )
    except Exception as e:
        log.warning(f"Telegram message failed: {e}")

def tg_send_file(path, caption=""):
    try:
        with open(path, "rb") as f:
            requests.post(
                f"https://api.telegram.org/bot{TG_TOKEN}/sendDocument",
                data={"chat_id": TG_CHAT_ID, "caption": caption},
                files={"document": (os.path.basename(path), f, "text/csv")},
                timeout=60,
            )
        log.info(f"Sent {path} to Telegram")
    except Exception as e:
        log.warning(f"Telegram file send failed: {e}")

# ── Utilities ─────────────────────────────────────────────────────────────────
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def domain_of(url):
    try:
        return urlparse(url).netloc.lower().replace("www.", "")
    except:
        return ""

def slug(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())

def name_email_match(name, email):
    """Returns True if email domain looks related to business name."""
    if not name or not email:
        return False
    try:
        domain = email.split("@")[1].split(".")[0]
    except:
        return False
    n = slug(name)
    d = slug(domain)
    if not n or not d:
        return False
    if d in n or n in d:
        return True
    ratio = SequenceMatcher(None, n, d).ratio()
    return ratio >= 0.5

def detect_platform(html, headers=None):
    text = html or ""
    for platform, sigs in PLATFORMS.items():
        for sig in sigs:
            if sig.lower() in text.lower():
                return platform
    return "Unknown"

def detect_industry(text):
    text_l = text.lower()
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        for kw in keywords:
            if kw in text_l:
                return industry
    return "General"

def extract_emails(text):
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    found = re.findall(pattern, text)
    # filter out image files and common non-email patterns
    exclude = re.compile(r"\.(png|jpg|jpeg|gif|svg|webp|css|js)$", re.I)
    return [e for e in found if not exclude.search(e)]

def extract_phones(text):
    pattern = r"(?:(?:\+44|0044|0)[\s\-\.]?(?:\d[\s\-\.]?){9,10})"
    return re.findall(pattern, text)

def extract_socials(html):
    soup = BeautifulSoup(html, "lxml")
    socials = {"facebook": "", "instagram": "", "twitter": "", "linkedin": "", "tiktok": ""}
    patterns = {
        "facebook":  r"facebook\.com/[^\"'\s>/?]+",
        "instagram": r"instagram\.com/[^\"'\s>/?]+",
        "twitter":   r"(?:twitter|x)\.com/[^\"'\s>/?]+",
        "linkedin":  r"linkedin\.com/(?:company|in)/[^\"'\s>/?]+",
        "tiktok":    r"tiktok\.com/@[^\"'\s>/?]+",
    }
    text = str(soup)
    for key, pat in patterns.items():
        m = re.search(pat, text, re.I)
        if m:
            socials[key] = "https://" + m.group(0)
    return socials

def extract_city(text):
    uk_cities = [
        "London","Manchester","Birmingham","Leeds","Liverpool","Sheffield",
        "Edinburgh","Glasgow","Bristol","Leicester","Coventry","Bradford",
        "Nottingham","Kingston upon Hull","Newcastle","Stoke","Southampton",
        "Brighton","Plymouth","Cardiff","Belfast","Norwich","Reading",
        "Derby","Wolverhampton","Sunderland","Swansea","Oxford","Cambridge",
        "Exeter","York","Bath","Aberdeen","Dundee","Inverness","Gloucester",
        "Chester","Hereford","Worcester","Chichester","Winchester","Salisbury",
        "Portsmouth","Bournemouth","Milton Keynes","Luton","Ipswich",
        "Peterborough","Northampton","Middlesbrough","Bolton","Blackburn",
    ]
    for city in uk_cities:
        if re.search(r"\b" + re.escape(city) + r"\b", text, re.I):
            return city
    return ""

def companies_house_lookup(name):
    """Optional — only if API key provided."""
    if not COMPANIES_HOUSE_KEY:
        return ""
    try:
        r = requests.get(
            "https://api.company-information.service.gov.uk/search/companies",
            params={"q": name, "items_per_page": 1},
            auth=(COMPANIES_HOUSE_KEY, ""),
            timeout=10,
        )
        items = r.json().get("items", [])
        if items:
            company = items[0]
            # Get director from officer endpoint
            number = company.get("company_number", "")
            if number:
                r2 = requests.get(
                    f"https://api.company-information.service.gov.uk/company/{number}/officers",
                    auth=(COMPANIES_HOUSE_KEY, ""),
                    timeout=10,
                )
                officers = r2.json().get("items", [])
                for o in officers:
                    if o.get("officer_role", "").lower() in ("director", "managing-director"):
                        return o.get("name", "").title()
    except:
        pass
    return ""

def is_uk_ecommerce(html, url):
    """Basic check: does this look like a UK e-commerce site?"""
    text = (html or "").lower()
    url_l = url.lower()
    # Must have shopping indicators
    shopping = any(kw in text for kw in [
        "add to cart", "add to basket", "buy now", "checkout",
        "shopping cart", "shopping basket", "place order", "add to bag",
        "£", "gbp",
    ])
    # UK indicators
    uk_indicators = any(kw in text or kw in url_l for kw in [
        ".co.uk", "united kingdom", "uk delivery", "uk shipping",
        "england", "scotland", "wales", "northern ireland",
        "royal mail", "hermes", "dpd uk", "evri",
    ])
    return shopping and (uk_indicators or ".co.uk" in url_l)

# ── Search engine scraping (DuckDuckGo) ──────────────────────────────────────
def ddg_search(page, query, max_results=20):
    """Scrape DuckDuckGo HTML search results."""
    urls = []
    try:
        encoded = quote_plus(query)
        page.goto(f"https://html.duckduckgo.com/html/?q={encoded}", timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(2, 4))
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a.result__url"):
            href = a.get("href", "")
            if href.startswith("http"):
                urls.append(href)
        # Also check result links
        for a in soup.select(".result__title a"):
            href = a.get("href", "")
            if "uddg=" in href:
                m = re.search(r"uddg=([^&]+)", href)
                if m:
                    from urllib.parse import unquote
                    urls.append(unquote(m.group(1)))
    except Exception as e:
        log.debug(f"DDG search error: {e}")
    return list(dict.fromkeys(urls))[:max_results]

def bing_search(page, query, max_results=20):
    """Scrape Bing search results."""
    urls = []
    try:
        encoded = quote_plus(query + " UK")
        page.goto(f"https://www.bing.com/search?q={encoded}&setlang=en-GB", timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(2, 4))
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        for h2 in soup.select("li.b_algo h2 a"):
            href = h2.get("href", "")
            if href.startswith("http") and "bing.com" not in href:
                urls.append(href)
    except Exception as e:
        log.debug(f"Bing search error: {e}")
    return list(dict.fromkeys(urls))[:max_results]

# ── Directory scraping ────────────────────────────────────────────────────────
def scrape_yell(page, category="online shop", page_num=1):
    urls = []
    try:
        url = f"https://www.yell.com/s/{quote_plus(category)}-united+kingdom.html?page={page_num}"
        page.goto(url, timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(2, 5))
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[data-tracking='businessName']"):
            href = a.get("href", "")
            if href:
                urls.append("https://www.yell.com" + href if href.startswith("/") else href)
        # Get actual business website from listing pages
        websites = []
        for listing_url in urls[:10]:
            try:
                page.goto(listing_url, timeout=PAGE_TIMEOUT)
                time.sleep(random.uniform(1, 3))
                html2 = page.content()
                soup2 = BeautifulSoup(html2, "lxml")
                for a2 in soup2.select("a[data-tracking='website']"):
                    href2 = a2.get("href", "")
                    if href2 and href2.startswith("http"):
                        websites.append(href2)
            except:
                pass
        return websites
    except Exception as e:
        log.debug(f"Yell scrape error: {e}")
    return urls

def scrape_freeindex(page, page_num=1):
    urls = []
    try:
        url = f"https://www.freeindex.co.uk/search.htm?q=online+shop&region=uk&p={page_num}"
        page.goto(url, timeout=PAGE_TIMEOUT)
        time.sleep(random.uniform(2, 4))
        html = page.content()
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select(".company-website a, a[rel='nofollow external']"):
            href = a.get("href", "")
            if href and href.startswith("http") and "freeindex" not in href:
                urls.append(href)
    except Exception as e:
        log.debug(f"FreeIndex scrape error: {e}")
    return urls

# ── Per-store data extraction ─────────────────────────────────────────────────
def extract_store_data(page, url, source):
    """Visit a store URL and extract all relevant data."""
    try:
        page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
        time.sleep(random.uniform(1, 3))
        html = page.content()
    except PWTimeout:
        return None, "timeout"
    except Exception as e:
        return None, str(e)[:100]

    if not html or len(html) < 500:
        return None, "empty_response"

    if not is_uk_ecommerce(html, url):
        return None, "not_uk_ecommerce"

    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)

    # Business name
    name = ""
    og_name = soup.find("meta", property="og:site_name")
    if og_name:
        name = og_name.get("content", "").strip()
    if not name:
        title = soup.find("title")
        if title:
            name = title.text.split("|")[0].split("-")[0].strip()
    if not name:
        h1 = soup.find("h1")
        if h1:
            name = h1.text.strip()

    # Try contact/about page for email + owner
    emails = extract_emails(html)
    owner = ""

    contact_urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"].lower()
        if any(kw in href for kw in ["contact", "about", "team", "us"]):
            full = urljoin(url, a["href"])
            if urlparse(full).netloc == urlparse(url).netloc:
                contact_urls.append(full)

    for curl in contact_urls[:3]:
        try:
            page.goto(curl, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
            time.sleep(random.uniform(1, 2))
            chtml = page.content()
            emails += extract_emails(chtml)
            # Try to find owner name
            csoup = BeautifulSoup(chtml, "lxml")
            ctext = csoup.get_text(" ", strip=True)
            # Look for "Founded by", "CEO", "Director", "Owner" patterns
            owner_patterns = [
                r"(?:founder|ceo|director|owner|managing director|established by)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
                r"([A-Z][a-z]+ [A-Z][a-z]+),?\s+(?:founder|ceo|director|owner)",
            ]
            for pat in owner_patterns:
                m = re.search(pat, ctext, re.I)
                if m:
                    owner = m.group(1).strip()
                    break
        except:
            pass

    # Companies House lookup for owner
    if not owner and name:
        owner = companies_house_lookup(name)

    # Deduplicate emails, prefer business domain
    base_domain = domain_of(url)
    emails = list(dict.fromkeys(emails))
    business_emails = [e for e in emails if base_domain.split(".")[0] in e.split("@")[-1] if "@" in e]
    generic_emails  = [e for e in emails if e not in business_emails]
    chosen_email = (business_emails or generic_emails or [""])[0]

    # Phone
    phones = extract_phones(text)
    phone = phones[0] if phones else ""

    # Socials
    socials = extract_socials(html)

    # Platform
    headers_text = ""
    try:
        resp = requests.head(url, timeout=8, allow_redirects=True)
        headers_text = str(resp.headers)
    except:
        pass
    platform = detect_platform(html + headers_text)

    # Industry / category
    meta_desc = ""
    md = soup.find("meta", attrs={"name": "description"})
    if md:
        meta_desc = md.get("content", "")
    industry = detect_industry(text + " " + meta_desc)

    # City
    city = extract_city(text)
    google_location = f"{city}, United Kingdom" if city else "United Kingdom"

    # Email verification
    email_verified = "Yes" if name_email_match(name, chosen_email) else "No"

    store = {
        "business_name":  name,
        "owner_name":     owner,
        "email":          chosen_email,
        "phone":          phone,
        "website":        url,
        "industry":       industry,
        "category":       "",
        "platform":       platform,
        "city":           city,
        "google_location": google_location,
        "facebook":       socials["facebook"],
        "instagram":      socials["instagram"],
        "twitter":        socials["twitter"],
        "linkedin":       socials["linkedin"],
        "tiktok":         socials["tiktok"],
        "email_verified": email_verified,
        "source":         source,
        "found_at":       now(),
    }
    return store, None

# ── Progress display ──────────────────────────────────────────────────────────
def print_banner(state):
    print("\033[2J\033[H", end="")  # clear screen
    print("=" * 70)
    print("  🇬🇧  UK E-COMMERCE STORE FINDER  |  Running 24/7")
    print("=" * 70)
    print(f"  Total stores found  : {state['total_found']}")
    print(f"  Current batch       : #{state['batch']} ({state['batch_count']}/{BATCH_SIZE})")
    print(f"  Broken sites logged : {state['broken_count']}")
    print(f"  Output directory    : {BASE_DIR}")
    print(f"  Last update         : {now()}")
    print("=" * 70)

def print_store(store):
    print(f"\n  ✅ {store['business_name']}")
    print(f"     {store['website']}")
    print(f"     Email: {store['email']} (verified: {store['email_verified']})")
    if store['owner_name']:
        print(f"     Owner: {store['owner_name']}")
    print(f"     {store['city']} | {store['platform']} | {store['industry']}")

def print_skip(url, reason):
    short = reason[:50] if reason else "unknown"
    print(f"  ⚠  SKIP  {url[:55]} — {short}")

def print_broken(url):
    print(f"  ❌ BROKEN {url[:60]}")

# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    os.makedirs(BASE_DIR, exist_ok=True)
    ensure_broken_csv()
    state = load_state()
    seen = set(state.get("seen_domains", []))
    query_idx = state.get("query_index", 0)
    dir_page  = state.get("dir_index", 1)

    tg_message(
        f"🚀 *UK E-commerce Scraper Started*\n"
        f"Batch #{state['batch']} | {state['total_found']} stores so far\n"
        f"Output: `{BASE_DIR}`"
    )

    ensure_batch_csv(state["batch"])

    def graceful_exit(sig, frame):
        log.info("Shutting down — saving state...")
        state["seen_domains"] = list(seen)[-5000:]  # keep last 5k to avoid huge state
        save_state(state)
        sys.exit(0)

    signal.signal(signal.SIGINT, graceful_exit)
    signal.signal(signal.SIGTERM, graceful_exit)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1366, "height": 768},
            locale="en-GB",
        )
        page = context.new_page()
        page.set_extra_http_headers({"Accept-Language": "en-GB,en;q=0.9"})

        url_queue = []
        source_map = {}

        while True:
            print_banner(state)

            # ── Refill queue if low ───────────────────────────────────────────
            if len(url_queue) < 10:
                # Rotate through search engines
                query = SEARCH_QUERIES[query_idx % len(SEARCH_QUERIES)]
                query_idx += 1
                state["query_index"] = query_idx

                print(f"\n  🔍 Searching: {query[:65]}")

                if query_idx % 3 == 0:
                    results = bing_search(page, query)
                    src = "bing"
                else:
                    results = ddg_search(page, query)
                    src = "duckduckgo"

                for u in results:
                    d = domain_of(u)
                    if d and d not in seen:
                        url_queue.append(u)
                        source_map[u] = src

                # Also scrape directories periodically
                if query_idx % 8 == 0:
                    print(f"  📒 Scraping Yell.com (page {dir_page})")
                    yell_urls = scrape_yell(page, "online shop", dir_page)
                    for u in yell_urls:
                        d = domain_of(u)
                        if d and d not in seen:
                            url_queue.append(u)
                            source_map[u] = "yell.com"

                if query_idx % 12 == 0:
                    print(f"  📒 Scraping FreeIndex.co.uk (page {dir_page})")
                    fi_urls = scrape_freeindex(page, dir_page)
                    for u in fi_urls:
                        d = domain_of(u)
                        if d and d not in seen:
                            url_queue.append(u)
                            source_map[u] = "freeindex.co.uk"
                    dir_page += 1
                    state["dir_index"] = dir_page

                delay = random.uniform(*SEARCH_DELAY)
                print(f"  ⏳ Waiting {delay:.0f}s before next search...")
                time.sleep(delay)

            # ── Process next URL ──────────────────────────────────────────────
            if not url_queue:
                time.sleep(5)
                continue

            url = url_queue.pop(0)
            d = domain_of(url)
            if d in seen:
                continue
            seen.add(d)

            print(f"\n  🌐 Checking: {url[:70]}")

            # Reset UA occasionally
            if state["total_found"] % 50 == 0:
                try:
                    context.close()
                    context = browser.new_context(
                        user_agent=random.choice(USER_AGENTS),
                        viewport={"width": 1366, "height": 768},
                        locale="en-GB",
                    )
                    page = context.new_page()
                    page.set_extra_http_headers({"Accept-Language": "en-GB,en;q=0.9"})
                except:
                    pass

            src = source_map.pop(url, "search")
            store, error = extract_store_data(page, url, src)

            if error:
                if error in ("timeout", "empty_response") or "ERR_" in error:
                    write_broken(url, error)
                    state["broken_count"] += 1
                    print_broken(url)
                else:
                    print_skip(url, error)
            else:
                append_store(state["batch"], store)
                state["total_found"] += 1
                state["batch_count"] += 1
                print_store(store)

                # Check if batch is complete
                if state["batch_count"] >= BATCH_SIZE:
                    completed_path = csv_path(state["batch"])
                    log.info(f"Batch {state['batch']} complete — sending to Telegram")
                    tg_send_file(
                        completed_path,
                        f"✅ Batch #{state['batch']} complete — {BATCH_SIZE} UK e-commerce stores\n"
                        f"Total found so far: {state['total_found']}",
                    )
                    state["batch"] += 1
                    state["batch_count"] = 0
                    ensure_batch_csv(state["batch"])
                    tg_message(f"📂 Starting batch #{state['batch']}...")

            # Save state periodically
            if state["total_found"] % 25 == 0:
                state["seen_domains"] = list(seen)[-5000:]
                save_state(state)

            delay = random.uniform(*SITE_DELAY)
            time.sleep(delay)

if __name__ == "__main__":
    main()
