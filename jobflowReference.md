# JobFlow — Reference Document (Updated)

## Environment
- MacBook Pro M4
- VSCode
- Firefox (no additional config needed — Vite + FastAPI work identically across browsers)
- Python 3.11+
- Node.js 18+

---

## Stack

### Scraper (current, standalone)
```
requests           sync HTTP — Greenhouse, Ashby, Lever, Workday (plain)
playwright         headless Chromium — Workday bot-protected tenants
sqlite3            local storage (jobflow.db)
concurrent.futures ThreadPoolExecutor for ATS scrapers
threading          thread-local SQLite connections
```

### Backend (Phase 2+)
```
FastAPI + uvicorn
SQLAlchemy 2.0
SQLite (local) → PostgreSQL (production path, one config line change)
httpx (async HTTP client)
APScheduler (ingest scheduling)
Pydantic v2 (request/response validation)
python-dotenv (env vars)
PyYAML (config files)
tenacity (retry + exponential backoff)
```

### Frontend
```
React 18
Vite
Plain CSS modules
Native fetch (wrapped in apiFetch utility)
```

### Resume Generation (current)
```
Jinja2             LaTeX templating — template.tex.j2
pdflatex           PDF compilation from .tex
Ollama (local)     LLM for resume tailoring (pluggable via abstract interface)
```

### LLM
```
Ollama (local, pluggable via abstract provider interface)
  Active model: mistral:7b-instruct
  Fallback:     llama3.2:1b
Future: openai.py, anthropic.py — drop-in replacements
```

---

## Project Structure
```
jobflow/
├── main.py                          # entry point — resume generation & tailoring
├── config/
│   └── default.yaml                 # resume config (bullets, jobs, skills limits, etc.)
├── resume/
│   ├── __init__.py
│   ├── llm.py                       # call_llm() + build_prompt() + build_tailored_prompt()
│   ├── resume_pdf.py                # ReportLab PDF builder (alternative, not currently used)
│   └── templates/
│       └── resume.tex.j2            # Jinja2 LaTeX template for resume rendering
├── data/
│   ├── jobflow.db                   # SQLite database (git-ignored)
│   └── companies.yaml               # company platform mappings
├── scraper.py                       # standalone scraper — Greenhouse, Ashby, Lever, Workday
├── ingest.py                        # job scraper orchestrator (Phase 2+)
├── input.txt                        # raw resume input for parsing/tailoring
├── test_job.txt                     # example job posting for testing
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── database.py          # engine, session, Base, init_db()
│   ├── models.py            # SQLAlchemy: Job, RawJob, UserInteraction, IngestLog
│   ├── schemas.py           # Pydantic request/response shapes
│   ├── ingest.py            # orchestrates scrapers, calls pipeline
│   ├── pipeline.py          # fetch_raw → normalize → persist (3 stages)
│   ├── filters.py           # keyword match, dedup, parse_location, parse_salary
│   ├── ranking.py           # ranking algorithm (stub → grows in Phase 5)
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── remotive.py      # global feed, no auth
│   │   ├── themuse.py       # global feed, no auth, paginated
│   │   ├── jobicy.py        # global feed, no auth
│   │   ├── adzuna.py        # global feed, free API key required
│   │   ├── greenhouse.py    # per-company, reads companies.yaml
│   │   ├── lever.py         # per-company, reads companies.yaml
│   │   ├── ashby.py         # per-company, reads companies.yaml
│   │   └── workday.py       # per-company — plain POST + headless fallback
│   └── llm/
│       ├── __init__.py
│       ├── provider.py      # abstract base class LLMProvider
│       └── ollama.py        # Ollama implementation
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx
│   │   ├── api.js
│   │   ├── components/
│   │   │   ├── JobList.jsx
│   │   │   ├── JobCard.jsx
│   │   │   ├── FilterBar.jsx
│   │   │   └── StatsBar.jsx
│   │   └── styles/
│   │       ├── global.css
│   │       ├── JobCard.module.css
│   │       └── FilterBar.module.css
│   ├── index.html
│   ├── vite.config.js       # proxies /api/* → localhost:8000
│   └── package.json
├── resume/
│   ├── resume_pdf.py        # ReportLab builder — PRIMARY, no external tools
│   ├── llm.py               # Ollama subprocess call + JSON prompt builder
│   └── templates/
│       └── jakes.html       # Jake's Resume HTML (kept as reference/fallback)
├── data/
│   ├── companies.yaml       # platform → slug mappings
│   └── jobflow.db           # SQLite database (git-ignored)
├── config/
│   └── default.yaml
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
└── README.md
```

---

## Scraper Architecture (`scraper.py`)

### ATS Source Lists
```python
GREENHOUSE_SOURCES    list[str]          ~60 company slugs
ASHBY_SOURCES         list[str]          ~60 company slugs
LEVER_SOURCES         list[str]          ~35 company slugs
WORKDAY_SOURCES_PLAIN  dict[str, tuple]  plain POST works — Intel, BMO (confirmed)
WORKDAY_SOURCES_HEADLESS dict[str, tuple] bot-protected — all others
```

### Workday — Two-Path Strategy
Workday tenants split into two groups based on whether they accept plain POST requests or require a real browser session to obtain auth cookies/tokens:

**Plain path** (`_workday_plain_worker`):
- `requests.Session` with browser-like headers
- POST to `/wday/cxs/{subdomain}/External/jobs`
- Payload: `{"appliedFacets": {}, "limit": 20, "offset": 0, "searchText": ""}`
- Paginates via `offset` until `offset >= total`
- Currently confirmed working: `intel`, `bmo`

**Headless path** (`fetch_workday_jobs_headless`):
- Single shared Chromium browser (Playwright), one context per company
- Navigates to `/External` careers page, intercepts XHR response containing first page
- Extracts `total` from intercepted response; paginates remaining pages via `page.evaluate()` fetch with `credentials: "include"` to reuse session cookies
- Anti-detection: `webdriver` property masked, plugins/languages spoofed, `window.chrome` injected
- All other Workday companies routed here

### Job Dataclass
```python
@dataclass
class Job:
    title:       str
    company:     str
    url:         str           # unique key / dedup field
    location:    str
    description: str
    date_posted: str
    apply_url:   Optional[str] # distinct from listing URL where applicable
    raw:         Optional[str] # full JSON blob from ATS API
```

### Universal Fetch Engine (`_fetch_jobs`)
All ATS workers pass raw API responses through a single `field_map` dict:
```python
field_map = {
    "title":     "title",           # key name, or...
    "loc":       lambda x: x[...],  # ...callable for nested fields
    "apply_url": None,              # None = omit
}
count = _fetch_jobs(company, raw_jobs, field_map)
```

### Database (`jobflow.db`)
```sql
CREATE TABLE IF NOT EXISTS jobs (
    url          TEXT PRIMARY KEY,   -- dedup key
    title        TEXT,
    company      TEXT,
    location     TEXT,
    description  TEXT,
    date_posted  TEXT,
    apply_url    TEXT,
    raw          TEXT,               -- full JSON blob
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
-- INSERT uses ON CONFLICT(url) DO UPDATE — safe to re-run anytime
```

---

## Resume Generation (Phase 1–2)

### Primary Path — LaTeX (`resume/templates/resume.tex.j2` + pdflatex)
Jinja2 templating with pdflatex compilation for professional PDF output.

```python
# Generic mode:
# 1. python main.py
# 2. Reads raw_text from input.txt
# 3. call_llm(build_prompt(raw_text)) → structured JSON
# 4. Render resume.tex.j2 with data → LaTeX
# 5. pdflatex → output/resume.pdf

# Tailored mode:
# 1. python main.py --job "job posting text" --company "TechCorp" --role "Senior Backend Engineer"
# 2. call_llm(build_tailored_prompt(raw_text, job_description, config)) → tailored JSON
# 3. LLM applies intelligent selection/rewriting based on job requirements
# 4. Render.tex.j2 with tailored data → LaTeX
# 5. pdflatex → output/techcorp_senior_backend_engineer_resume.pdf
```

**JSON Schema** (returned by LLM):
```python
{
    "name":       str,
    "email":      str,
    "phone":      str,
    "linkedin":   str,
    "github":     str,        # optional
    "summary":    str,        # optional
    "experience": [
        {
            "title":      str,
            "company":    str,
            "location":   str,
            "start_date": str,
            "end_date":   str,   # defaults to "Present"
            "bullets":    [str]  # tailored to job when --job provided
        }
    ],
    "education": [
        {"degree": str, "institution": str, "year": str}
    ],
    "skills": [str],           # filtered/reordered by relevance
    "projects": [              # optional, included when relevant to job
        {
            "name":          str,
            "description":   str,
            "technologies":  [str]
        }
    ]
}
```

### CLI Usage

```bash
# Generic resume parsing (no tailoring)
python main.py

# Tailored resume for specific job
python main.py \
  --job "$(cat job_posting.txt)" \
  --company "TechCorp" \
  --role "Senior Backend Engineer"

# Custom config and input paths
python main.py \
  --job "job description" \
  --company "StartupXYZ" \
  --role "ML Engineer" \
  --input my_resume.txt \
  --config custom_config.yaml \
  --output-dir tailored_resumes/
```

**Output naming**:
- Generic: `output/resume.pdf`
- Tailored: `output/{company}_{role}_resume.pdf` (sanitized)


### LLM Layer (`llm.py`)
```python
active_model = "mistral:7b-instruct"   # swap to llama3.2:1b for speed

def call_llm(prompt: str) -> dict:
    # runs: ollama run {model} < prompt
    # returns: parsed JSON dict

def build_prompt(raw_text: str) -> str:
    # instructs model to return ONLY valid JSON matching resume data shape
    # no preamble, no markdown fences
```

### Resume Pipeline (Current flow)
```
1. User runs: python main.py
2. Reads raw_text from input.txt
3. build_prompt(raw_text) → call_llm() → structured JSON dict
4. Trim bullets: job["bullets"] = job["bullets"][:max_bullets]  (from config)
5. Render template.tex.j2 with Jinja2
6. Write output/resume.tex
7. pdflatex → output/resume.pdf
```

---

## Database (Full schema — Phase 2 FastAPI backend)

### `jobs`
```
id                  INTEGER         PK autoincrement
title               TEXT            NOT NULL
company             TEXT            NOT NULL
url                 TEXT            NOT NULL UNIQUE
description         TEXT
location_raw        TEXT
location_city       TEXT
location_state      TEXT
location_country    TEXT            default "US"
is_remote           BOOLEAN         default False
salary_raw          TEXT
salary_min          INTEGER         USD cents
salary_max          INTEGER         USD cents
salary_currency     TEXT            default "USD"
employment_type     TEXT
date_posted         DATETIME        UTC
source              TEXT            NOT NULL
keywords_matched    JSON
is_active           BOOLEAN         default True
created_at          DATETIME        default utcnow
updated_at          DATETIME        default utcnow
```

### `raw_jobs`
```
id          INTEGER     PK
source      TEXT
raw_data    JSON
fetched_at  DATETIME    default utcnow
normalized  BOOLEAN     default False
error       TEXT        nullable
```

### `user_interactions`
```
id                  INTEGER     PK
job_id              INTEGER     FK → jobs.id UNIQUE
score               INTEGER     1-5, null = unrated
is_saved            BOOLEAN     default False
is_hidden           BOOLEAN     default False
applied_at          DATETIME    nullable
time_viewed_seconds INTEGER     default 0
view_count          INTEGER     default 0
notes               TEXT        nullable
created_at          DATETIME    default utcnow
updated_at          DATETIME    default utcnow
```

### `ingest_logs`
```
id           INTEGER     PK
started_at   DATETIME
finished_at  DATETIME    nullable
jobs_fetched INTEGER     default 0
jobs_added   INTEGER     default 0
jobs_skipped INTEGER     default 0
status       TEXT        running | complete | failed
error        TEXT        nullable
```

---

## API Routes (Phase 2)
```
GET  /api/jobs                   paginated list
                                 params: keyword, source, company,
                                 city, state, remote, employment_type,
                                 date_since, page, page_size

GET  /api/jobs/{id}              single job + interaction data
PUT  /api/jobs/{id}/interaction  upsert: score, is_saved, is_hidden, notes
GET  /api/jobs/sources           distinct sources in DB
GET  /api/jobs/companies         distinct companies in DB

POST /api/ingest                 trigger full scrape (background task)
GET  /api/ingest/status          most recent ingest_log row

GET  /api/stats                  totals by source, keyword freq,
                                 jobs last 24h, last ingest timestamp
```

---

## Scraper Contract (Phase 2 backend scrapers)
```python
async def fetch_raw(keywords: list[str], config: dict) -> list[dict]
# - hits API
# - returns raw dicts exactly as received
# - never writes to DB, never normalizes
# - raises on unrecoverable error; tenacity handles retries
```

---

## Pipeline Stages (`pipeline.py`)
```
Stage 1 — fetch_raw()
  scraper returns list[dict]
  written to raw_jobs, normalized=False

Stage 2 — normalize()
  raw dict → Job-shaped dict
  parse_location(), parse_salary(), match_keywords()
  errors → raw_jobs.error, row skipped

Stage 3 — persist()
  dedup on jobs.url
  write new rows to jobs
  flip raw_jobs.normalized = True
```

---

## Config Files

### `.env`
```
DATABASE_URL=sqlite:///./data/jobflow.db
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral:7b-instruct
LOG_LEVEL=INFO
```

### `default.yaml`
```yaml
ingestion:
  keywords:
    - Python
    - Software Engineer
    - Software Developer
    - AI Engineer
    - Machine Learning Engineer
    - Backend Engineer
    - Full Stack Engineer
    - Data Engineer
  max_pages: 5
  request_timeout: 10
  sources:
    remotive: true
    themuse: true
    jobicy: true
    adzuna: true
    greenhouse: true
    lever: true
    ashby: true
    workday: true

rate_limits:
  greenhouse:   { delay: 0.5, max_concurrent: 10, retry_attempts: 3 }
  ashby:        { delay: 0.5, max_concurrent: 10, retry_attempts: 3 }
  lever:        { delay: 0.5, max_concurrent: 10, retry_attempts: 3 }
  workday_plain:    { delay: 1.0, max_concurrent: 5,  retry_attempts: 3 }
  workday_headless: { delay: 2.0, max_concurrent: 1,  retry_attempts: 2 }

resume:
  max_bullets: 4
  model: mistral:7b-instruct
  output_dir: output/

schedule:
  enabled: false
  interval_hours: 6
  run_on_startup: false

server:
  host: 127.0.0.1
  port: 8000

defaults:
  currency: USD
  timezone: America/Toronto
  country: CA
```

### `companies.yaml`
```yaml
greenhouse:
  - stripe
  - notion
  - figma
  - discord
  - coinbase
  - brex
  - retool
  - airtable
  # ... ~60 total, see GREENHOUSE_SOURCES in scraper.py

lever:
  - airbnb
  - reddit
  - lyft
  - instacart
  - carta
  - klaviyo
  # ... ~35 total, see LEVER_SOURCES in scraper.py

ashby:
  - supabase
  - linear
  - vercel
  - anthropic
  - openai
  # ... ~60 total, see ASHBY_SOURCES in scraper.py

workday:
  plain:
    - intel
    - bmo
  headless:
    - amazon
    - google
    - microsoft
    - apple
    - shopify
    - rbc
    - td
    # ... full list in WORKDAY_SOURCES_HEADLESS in scraper.py
```

---

## Dev Workflow

### Resume Pipeline (Current — Phase 1–2)
```bash
# Generic resume parsing
python main.py

# Tailored resume for specific job
python main.py \
  --job "$(cat test_job.txt)" \
  --company "TechCorp" \
  --role "Senior Backend Engineer"

# Custom paths
python main.py \
  --job "job posting" \
  --company "StartupXYZ" \
  --role "ML Engineer" \
  --input my_resume.txt \
  --config config/custom.yaml
```

### Job Scraper (Phase 2+)
```bash
# Standalone scrape (no backend needed)
python scraper.py                    # writes to data/jobflow.db
python ingest.py                     # orchestrate full pipeline
```

### Backend + Frontend (Phase 3 — Now Implemented)

**Backend API** (`backend.py` via FastAPI):
```bash
# Terminal 1: Start backend API (serves jobs from jobflow.db)
source .venv/bin/activate
python -m uvicorn backend:app --reload --port 8000
```

**API Endpoints**:
- `GET /` — Health check
- `GET /api/jobs` — List jobs with pagination & filters
  - Query params: `keyword`, `company`, `location`, `page`, `page_size`
- `GET /api/jobs/{job_url}` — Get single job details
- `GET /api/jobs/filters/companies` — Distinct companies
- `GET /api/jobs/filters/locations` — Distinct locations  
- `POST /api/tailor` — Generate tailored resume for a job
  - Body: `job_url`, `company`, `role`, `input_file`, `config_file`

**Frontend** (`frontend/` — React 18 + Vite):
```bash
# Terminal 2: Start frontend dev server
cd frontend
npm install           # (one-time)
npm run dev          # Vite on :5173
```

**Features**:
- Browse 12,000+ scraped jobs from jobflow.db
- Filter by keyword, company, location
- Click job to view details + apply link
- Generate tailored resume for that job
- Download generated PDF

**Full Stack Startup**:
```bash
# Terminal 1: Backend
source .venv/bin/activate
python -m uvicorn backend:app --reload --port 8000

# Terminal 2: Frontend
cd frontend
npm run dev

# Browser: http://localhost:5173
```

## Production Build
```
cd frontend && npm run build         # outputs frontend/dist/
FastAPI mounts dist/ as StaticFiles at "/"
Single process: uvicorn backend.main:app --port 8000
Browser: localhost:8000
```

---

## Build Phases

```
Phase 1 ✅  scraper.py live
            Greenhouse, Ashby, Lever — threaded, working
            Workday plain — Intel, BMO confirmed
            Workday headless — Playwright, bot-detection bypassed
            jobflow.db — 10,000+ jobs indexed across 100+ companies

Phase 2     database.py, models.py (SQLAlchemy)
            pipeline.py — fetch_raw → normalize → persist
            filters.py — keyword match, dedup, parse_location, parse_salary
            ingest.py — orchestrator

Phase 3     main.py + schemas.py — all FastAPI routes live
            Goal: query jobs via localhost:8000/docs

Phase 4     React frontend — JobList, FilterBar, JobCard, StatsBar
            Goal: browsable UI with filtering

Phase 5     ranking.py — weighted scoring, implicit signals
            Goal: relevant jobs surface first

Phase 6     Resume pipeline
            LLM (Ollama/mistral) → structured JSON → ReportLab PDF
            Input: job URL + existing resume text
            Output: tailored single-page PDF
            No LaTeX. No pdflatex. No external binaries.
```