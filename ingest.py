import requests
import sqlite3
import time
import json
import re
import threading
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# --- Configuration & Sources ---


GREENHOUSE_SOURCES = list(set(s.lower() for s in [
    "airbnb", "elastic", "spacex", "lyft", "gitlab", "figma",
    "coinbase", "asana", "dropbox", "discord", "cloudflare", "datadog",
    "instacart", "stripe", "pinterest", "smartsheet", "robinhood",
    "reddit", "airtable", "twilio", "okta", "hubspot", "wayfair",
    "peloton", "hellofresh", "podium", "duolingo", "benchling", "gong",
    "block", "trivago", "palantir", "zendesk", "intercom", "pagerduty",
    "squarespace", "etsy", "chime", "faire", "toast", "nerdwallet",
    "sofi", "marqeta", "brex", "plaid", "vanta", "launchdarkly",
    "retool", "gusto", "lattice", "rippling", "deel", "samsara",
    "scale", "confluent", "cockroachdb", "dbt", "mongodb", "1password",
    "sendbird", "mixpanel", "amplitude", "segment", "betterment",
    "navan", "procore", "veeva", "shopify", "wealthsimple", "lightspeed",
    "nuvei", "docebo", "dapperlabs", "hootsuite", "clio", "coveo",
    "benevity", "absorblms", "vendasta", "clearco", "koho", "wagepoint",
]))
ASHBY_SOURCES = list(set(s.lower() for s in [
    "linear", "raycast", "modal", "cursor", "neon", "supabase",
    "inngest", "wealthsimple", "clerk", "render", "leapsome",
    "notion", "cohere", "perplexity", "ramp", "resend",
    "plaid", "elevenlabs", "deel", "replit", "anthropic", "openai",
    "anduril", "applied-intuition", "arc", "watershed", "mercury",
    "brex", "pilot", "midjourney", "runway", "character", "adept",
    "mistral", "vercel", "turso", "novu", "dbt-labs", "hightouch",
    "census", "hex", "eppo", "statsig", "posthog", "june",
    "liveblocks", "tinybird", "motherduck", "fal", "together",
    "fireworks", "baseten", "helicone", "braintrust", "langfuse",
    "scale", "labelbox", "humanloop", "vanta", "drata", "secureframe",
    "launchdarkly", "retool", "superblocks", "clio", "dapperlabs",
    "properly", "norm-ai",
]))
LEVER_SOURCES = list(set(s.lower() for s in [
    "spotify", "metabase", "palantir", "crypto", "gohighlevel",
    "weride", "morningbrew", "wintermute-trading", "netflix", "affirm",
    "flexport", "nuro", "aurora", "joby", "zoox", "relativity",
    "astranis", "samsara", "verkada", "procore", "medallia",
    "qualtrics", "sprinklr", "navan", "toast", "benchling",
    "rippling", "lattice", "wealthsimple", "hootsuite", "clio",
    "lightspeed-hq", "ritual", "koho", "borrowell", "nesto",
]))
WORKDAY_SOURCES_PLAIN = {
    "intel": ("intel", "wd1"),
    "bmo":   ("bmo",   "wd3"),
}
WORKDAY_SOURCES_HEADLESS = {
    "amazon":       ("amazon",          "wd1"),
    "jpmorgan":     ("jpmorgan",        "wd1"),
    "apple":        ("apple-talent",    "wd5"),
    "microsoft":    ("microsoft",       "wd5"),
    "google":       ("google",          "wd3"),
    "meta":         ("meta",            "wd5"),
    "ibm":          ("ibm",             "wd5"),
    "oracle":       ("oracle",          "wd1"),
    "salesforce":   ("salesforce",      "wd1"),
    "amd":          ("amd",             "wd1"),
    "qualcomm":     ("qualcomm",        "wd5"),
    "deloitte":     ("deloitte",        "wd1"),
    "accenture":    ("accenture",       "wd3"),
    "kpmg":         ("kpmg",            "wd1"),
    "mckinsey":     ("mckinsey",        "wd5"),
    "goldman":      ("goldmansachs",    "wd1"),
    "bofa":         ("bankofamerica",   "wd1"),
    "wells":        ("wellsfargo",      "wd5"),
    "lockheed":     ("lmco",            "wd1"),
    "uber":         ("uber",            "wd5"),
    "servicenow":   ("servicenow",      "wd5"),
    "snowflake":    ("snowflake",       "wd1"),
    "shopify":      ("shopify",         "wd1"),
    "scotiabank":   ("scotiabank",      "wd3"),
    "cgi":          ("cgi",             "wd1"),
    "opentext":     ("opentext",        "wd1"),
    "telus":        ("telus",           "wd3"),
    "bell":         ("bell",            "wd1"),
    "rogers":       ("rogers",          "wd3"),
    "bombardier":   ("bombardier",      "wd1"),
    "walmart":      ("walmart",         "wd1"),
    "nvidia":       ("nvidia",          "wd3"),
    "cisco":        ("cisco",           "wd3"),
    "pwc":          ("pwc",             "wd1"),
    "citi":         ("citi",            "wd1"),
    "boeing":       ("boeing",          "wd5"),
    "netflix":      ("netflix",         "wd5"),
    "adobe":        ("adobe",           "wd3"),
    "zoom":         ("zoom",            "wd1"),
    "workday":      ("workday",         "wd1"),
    "td":           ("td",              "wd1"),
    "rbc":          ("rbc",             "wd1"),
    "cibc":         ("cibc",            "wd1"),
    "manulife":     ("manulife",        "wd1"),
    "sunlife":      ("sunlife",         "wd1"),
    "suncor":       ("suncor",          "wd3"),
}

# --- Dataclass ---

@dataclass
class Job:
    title:       str
    company:     str
    url:         str
    location:    str
    description: str
    date_posted: str
    apply_url:   Optional[str] = None  # direct application URL, distinct from listing URL
    raw:         Optional[str] = None  # full JSON blob from the ATS API

# --- Database ---

_thread_local = threading.local()

def _get_thread_conn():
    if not hasattr(_thread_local, "conn"):
        _thread_local.conn = sqlite3.connect("jobflow.db", check_same_thread=False)
    return _thread_local.conn

def DatabaseSetup():
    conn = sqlite3.connect("jobflow.db")
    conn.execute('''
        CREATE TABLE IF NOT EXISTS jobs (
            url          TEXT PRIMARY KEY,
            title        TEXT,
            company      TEXT,
            location     TEXT,
            description  TEXT,
            date_posted  TEXT,
            apply_url    TEXT,
            raw          TEXT,
            extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    return conn

def save_jobs(conn, jobs: List[Job]):
    cursor = conn.cursor()
    cursor.executemany('''
        INSERT INTO jobs (url, title, company, location, description, date_posted, apply_url, raw)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title       = excluded.title,
            location    = excluded.location,
            description = excluded.description,
            date_posted = excluded.date_posted,
            apply_url   = excluded.apply_url,
            raw         = excluded.raw
    ''', [(
        j.url, j.title, j.company, j.location, j.description,
        j.date_posted, j.apply_url, j.raw
    ) for j in jobs])
    conn.commit()

# --- Universal Fetch Engine ---

GREEN, RED, RESET = "\033[92m", "\033[91m", "\033[0m"
_print_lock = threading.Lock()

def _safe_print(msg: str):
    with _print_lock:
        print(msg)

def _fetch_jobs(company: str, raw_jobs: List[Dict], field_map: Dict) -> int:
    job_batch = []
    skipped = 0
    for item in raw_jobs:
        def get(key, i=item):
            v = field_map.get(key)
            if v is None:   return None
            if callable(v): return v(i)
            return i.get(v)

        job = Job(
            title       = get("title"),
            company     = company,
            url         = get("url"),
            location    = get("loc"),
            description = get("desc"),
            date_posted = get("date"),
            apply_url   = get("apply_url"),
            raw         = json.dumps(item),
        )
        # Only include jobs with essential fields
        if job.url and job.title and job.description and job.date_posted:
            job_batch.append(job)
        else:
            skipped += 1

    if job_batch:
        save_jobs(_get_thread_conn(), job_batch)
    if skipped > 0:
        _safe_print(f"  (Skipped {skipped} incomplete jobs)")
    return len(job_batch)

# --- ATS Worker Functions ---

def _greenhouse_worker(token: str):
    field_map = {
        "title":     "title",
        "url":       "absolute_url",
        "loc":       lambda x: x.get("location", {}).get("name"),
        "desc":      "content",
        "date":      "updated_at",
        "apply_url": "absolute_url",  # Greenhouse listing URL doubles as apply URL
    }
    try:
        url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        raw_jobs = response.json().get("jobs", [])
        if not raw_jobs:
            return
        count = _fetch_jobs(token, raw_jobs, field_map)
        _safe_print(f"{GREEN}  [+] {token:.<20} Saved {count} jobs{RESET}")
    except Exception as e:
        _safe_print(f"{RED}  [!] {token:.<20} Error: {e}{RESET}")


def _ashby_worker(token: str):
    field_map = {
        "title":     "title",
        "url":       "jobUrl",
        "loc":       "location",
        "desc":      "descriptionHtml",
        "date":      "publishedAt",
        "apply_url": "applicationFormUrl",  # Ashby separates listing from apply form
    }
    try:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{token}"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        raw_jobs = response.json().get("jobs", [])
        if not raw_jobs:
            return
        count = _fetch_jobs(token, raw_jobs, field_map)
        _safe_print(f"{GREEN}  [+] {token:.<20} Saved {count} jobs{RESET}")
    except Exception as e:
        _safe_print(f"{RED}  [!] {token:.<20} Error: {e}{RESET}")


def _lever_worker(token: str):
    field_map = {
        "title":     "text",
        "url":       "hostedUrl",
        "loc":       lambda x: x.get("categories", {}).get("location"),
        "desc":      "descriptionPlain",
        "date":      "createdAt",
        "apply_url": "applyUrl",  # Lever provides a distinct apply URL
    }
    try:
        url = f"https://api.lever.co/v0/postings/{token}?mode=json"
        response = requests.get(url, timeout=12)
        response.raise_for_status()
        raw_jobs = response.json()
        if not raw_jobs:
            return
        count = _fetch_jobs(token, raw_jobs, field_map)
        _safe_print(f"{GREEN}  [+] {token:.<20} Saved {count} jobs{RESET}")
    except Exception as e:
        _safe_print(f"{RED}  [!] {token:.<20} Error: {e}{RESET}")


def _fetch_workday_job_details(url: str, timeout: int = 10) -> str:
    """Fetch full job description from Workday job detail page."""
    try:
        time.sleep(0.2)  # Rate limiting to be respectful to servers
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=timeout)
        response.encoding = 'utf-8'
        
        # Look for job description in common Workday HTML patterns
        if 'jobDescriptionText' in response.text or 'description' in response.text.lower():
            # Try to find description in script tags or divs
            import re
            desc_match = re.search(r'"description":\s*"([^"]+)"', response.text)
            if desc_match:
                desc = desc_match.group(1).replace('\\n', ' ')[:2000]
                return desc if desc.strip() else None
            
            # Alternative: look for common job description sections
            desc_match = re.search(r'<div[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)<', response.text, re.IGNORECASE)
            if desc_match:
                desc = desc_match.group(1).strip()[:2000]
                return desc if desc.strip() else None
    except Exception as e:
        pass
    return None

def _workday_plain_worker(company: str, subdomain: str, wd_version: str):
    field_map = {
        "title":     "title",
        "url":       "url",
        "loc":       "locationsText",
        "desc":      lambda x: _fetch_workday_job_details(x.get("url")) if x.get("url") else None,
        "date":      "postedOn",
        "apply_url": None,  # Workday listing URL and apply URL are the same page
    }
    api_url = (
        f"https://{subdomain}.{wd_version}.myworkdayjobs.com"
        f"/wday/cxs/{subdomain}/External/jobs"
    )
    payload = {"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}
    all_raw = []
    try:
        session = requests.Session()
        session.headers.update({
            "User-Agent":   "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept":       "application/json",
            "Content-Type": "application/json",
        })
        while True:
            response = session.post(api_url, json=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
            postings = data.get("jobPostings", [])
            if not postings:
                break
            base = f"https://{subdomain}.{wd_version}.myworkdayjobs.com"
            for job in postings:
                job["url"] = f"{base}/External{job.get('externalPath', '')}"
            all_raw.extend(postings)
            payload["offset"] += len(postings)
            if payload["offset"] >= data.get("total", 0):
                break
            time.sleep(1)

        if not all_raw:
            _safe_print(f"{RED}  [!] {company:.<20} No jobs found{RESET}")
            return
        count = _fetch_jobs(company, all_raw, field_map)
        _safe_print(f"{GREEN}  [+] {company:.<20} Saved {count} jobs{RESET}")
    except Exception as e:
        _safe_print(f"{RED}  [!] {company:.<20} Error: {e}{RESET}")

# --- Threaded ATS Fetchers ---

def fetch_greenhouse_jobs(sources: List[str], max_workers: int = 10):
    print(f"\n>>> Scouring GREENHOUSE Boards...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_greenhouse_worker, sources)

def fetch_ashby_jobs(sources: List[str], max_workers: int = 10):
    print(f"\n>>> Scouring ASHBY Boards...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_ashby_worker, sources)

def fetch_lever_jobs(sources: List[str], max_workers: int = 10):
    print(f"\n>>> Scouring LEVER Boards...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(_lever_worker, sources)

def fetch_workday_jobs(sources: Dict[str, tuple], max_workers: int = 5):
    print(f"\n>>> Scouring WORKDAY Boards (plain)...")
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        executor.map(lambda item: _workday_plain_worker(item[0], *item[1]), sources.items())

def fetch_workday_jobs_headless(sources: Dict[str, tuple], db_conn):
    print(f"\n>>> Scouring WORKDAY Boards (headless)...")

    field_map = {
        "title":     "title",
        "url":       "url",
        "loc":       "locationsText",
        "desc":      lambda x: _fetch_workday_job_details(x.get("url")) if x.get("url") else None,
        "date":      "postedOn",
        "apply_url": None,
    }

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
            ]
        )

        for company, (subdomain, wd_version) in sources.items():
            base_url = f"https://{subdomain}.{wd_version}.myworkdayjobs.com"
            api_url  = f"{base_url}/wday/cxs/{subdomain}/External/jobs"
            all_raw  = []
            intercepted_responses = []

            try:
                context = browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    },
                    java_script_enabled=True,
                    bypass_csp=True,
                )
                context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
                    window.chrome = { runtime: {} };
                """)

                page = context.new_page()

                def handle_response(response):
                    if "/wday/cxs/" in response.url and "/jobs" in response.url:
                        try:
                            intercepted_responses.append(response.json())
                        except Exception:
                            pass

                page.on("response", handle_response)

                try:
                    page.goto(f"{base_url}/External", wait_until="networkidle", timeout=45000)
                except PlaywrightTimeoutError:
                    page.wait_for_timeout(5000)

                for data in intercepted_responses:
                    postings = data.get("jobPostings", [])
                    for job in postings:
                        job["url"] = f"{base_url}/External{job.get('externalPath', '')}"
                    all_raw.extend(postings)

                if all_raw:
                    total  = intercepted_responses[0].get("total", 0) if intercepted_responses else 0
                    offset = len(all_raw)
                    while offset < total:
                        payload = {"appliedFacets": {}, "limit": 20, "offset": offset, "searchText": ""}
                        result  = page.evaluate("""
                            async ([url, payload]) => {
                                const res = await fetch(url, {
                                    method: "POST",
                                    headers: { "Content-Type": "application/json" },
                                    body: JSON.stringify(payload),
                                    credentials: "include"
                                });
                                if (!res.ok) throw new Error(`HTTP ${res.status}`);
                                return await res.json();
                            }
                        """, [api_url, payload])
                        postings = result.get("jobPostings", [])
                        if not postings:
                            break
                        for job in postings:
                            job["url"] = f"{base_url}/External{job.get('externalPath', '')}"
                        all_raw.extend(postings)
                        offset += len(postings)
                        time.sleep(1)

                context.close()

                if not all_raw:
                    print(f"{RED}  [!] {company:.<20} No jobs found (bot protection likely){RESET}")
                    continue

                count = _fetch_jobs(company, all_raw, field_map)
                print(f"{GREEN}  [+] {company:.<20} Saved {count} jobs{RESET}")

            except Exception as e:
                print(f"{RED}  [!] {company:.<20} Error: {e}{RESET}")
                try:
                    context.close()
                except Exception:
                    pass

        browser.close()

# --- Execution ---

if __name__ == "__main__":
    db_conn = DatabaseSetup()

    fetch_greenhouse_jobs(GREENHOUSE_SOURCES)
    fetch_ashby_jobs(ASHBY_SOURCES)
    fetch_lever_jobs(LEVER_SOURCES)
    fetch_workday_jobs(WORKDAY_SOURCES_PLAIN)
    fetch_workday_jobs_headless(WORKDAY_SOURCES_HEADLESS, db_conn)

    db_conn.close()
    print("\n✨ Ingestion complete. Database 'jobflow.db' is up to date.")