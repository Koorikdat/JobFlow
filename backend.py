"""
FastAPI backend for JobFlow — serves jobs from database and handles resume tailoring.
"""
import sqlite3
import json
from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import subprocess
import os
from pathlib import Path

app = FastAPI(title="JobFlow API", version="1.0.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database config
DB_PATH = Path("jobflow.db")  # Jobs database with scraped jobs


# ── Models ────────────────────────────────────────────────────────────────────
class Job(BaseModel):
    url: str  # Primary key
    title: str
    company: str
    location: str
    description: str
    date_posted: str


class JobDetail(Job):
    apply_url: Optional[str]
    raw: Optional[str]


class TailorRequest(BaseModel):
    job_url: str
    company: str
    role: str
    input_file: str = "data/input.txt"
    config_file: str = "config/default.yaml"


# ── Database helpers ──────────────────────────────────────────────────────────
def get_db_connection():
    """Get SQLite connection with row factory."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def get_job_by_url(url: str) -> Optional[dict]:
    """Fetch single job from database by URL."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT url, title, company, location, description, date_posted, apply_url, raw
        FROM jobs WHERE url = ?
        """,
        (url,),
    )
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def search_jobs(
    keyword: Optional[str] = None,
    company: Optional[str] = None,
    location: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[List[dict], int]:
    """Search jobs with filters."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT url, title, company, location, description, date_posted FROM jobs WHERE 1=1"
    params = []

    if keyword:
        query += " AND (description LIKE ? OR title LIKE ?)"
        pattern = f"%{keyword}%"
        params.extend([pattern, pattern])

    if company:
        query += " AND company LIKE ?"
        params.append(f"%{company}%")

    if location:
        query += " AND location LIKE ?"
        params.append(f"%{location}%")

    # Get total count
    count_query = query.replace(
        "SELECT url, title, company, location, description, date_posted",
        "SELECT COUNT(*) as cnt",
    )
    cursor.execute(count_query, params)
    total = cursor.fetchone()["cnt"]

    # Get paginated results
    query += " ORDER BY date_posted DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows], total


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "message": "JobFlow API running"}


@app.get("/api/jobs", response_model=dict)
def list_jobs(
    keyword: Optional[str] = Query(None),
    company: Optional[str] = Query(None),
    location: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """List jobs with filtering and pagination."""
    offset = (page - 1) * page_size
    jobs, total = search_jobs(
        keyword=keyword, company=company, location=location, limit=page_size, offset=offset
    )
    return {
        "jobs": jobs,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size,
    }


# ── Filter routes (MUST come before {job_url} catch-all) ──────────────────────
@app.get("/api/jobs/filters/companies")
def get_companies():
    """Get distinct companies in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT company FROM jobs ORDER BY company")
    companies = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"companies": companies}


@app.get("/api/jobs/filters/locations")
def get_locations():
    """Get distinct locations in database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT location FROM jobs WHERE location IS NOT NULL ORDER BY location")
    locations = [row[0] for row in cursor.fetchall()]
    conn.close()
    return {"locations": locations}


# ── Detail route (generic catch-all, MUST come last) ───────────────────────────
@app.get("/api/jobs/{job_url:path}", response_model=JobDetail)
def get_job(job_url: str):
    """Get single job details by URL."""
    job = get_job_by_url(job_url)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@app.post("/api/tailor")
def tailor_resume(request: TailorRequest):
    """Generate tailored resume for a job."""
    job = get_job_by_url(request.job_url)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Extract job description
    job_description = f"""
Title: {job['title']}
Company: {job['company']}
Location: {job['location']}

Description:
{job['description']}
"""

    # Call main.py with job tailoring
    try:
        result = subprocess.run(
            [
                "python",
                "main.py",
                "--job",
                job_description,
                "--company",
                request.company,
                "--role",
                request.role,
                "--input",
                request.input_file,
                "--config",
                request.config_file,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        if result.returncode != 0:
            raise HTTPException(
                status_code=500,
                detail=f"Resume generation failed: {result.stderr}",
            )

        # Return path to generated PDF
        safe_company = request.company.lower().replace(" ", "_")
        safe_role = request.role.lower().replace(" ", "_")
        pdf_name = f"{safe_company}_{safe_role}_resume.pdf"

        return {
            "status": "success",
            "pdf": f"output/{pdf_name}",
            "message": "Resume tailored successfully",
        }

    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=500, detail="Resume generation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/api/download/{filename}")
def download_resume(filename: str):
    """Download generated resume PDF."""
    pdf_path = Path("output") / filename
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    return {"path": str(pdf_path), "filename": filename}


@app.post("/api/admin/ingest")
def run_ingest():
    """Run ingest.py to fetch and repopulate job database."""
    try:
        # Run ingest.py in subprocess
        result = subprocess.run(
            ["python", "ingest.py"],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minute timeout
            cwd=Path(__file__).parent,
        )
        
        # Return both stdout and stderr for debugging
        return {
            "status": "success" if result.returncode == 0 else "error",
            "message": "Database ingestion completed",
            "return_code": result.returncode,
            "output": result.stdout[-500:] if result.stdout else "",  # Last 500 chars
            "errors": result.stderr[-500:] if result.stderr else "",  # Last 500 chars
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Ingestion timed out after 10 minutes")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ingestion error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
