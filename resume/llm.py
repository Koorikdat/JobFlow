import subprocess
import json
import yaml

active_model = "mistral:7b-instruct"
# active_model = "llama3.2:1b"


def call_llm(prompt: str) -> dict:
    """Call Ollama with the given prompt and parse JSON response."""
    result = subprocess.run(
        ["ollama", "run", active_model],
        input=prompt,
        text=True,
        capture_output=True
    )
    output = result.stdout.strip()
    
    # Extract JSON from output (handles cases where model returns extra text)
    json_str = extract_json(output)
    return json.loads(json_str)


def extract_json(text: str) -> str:
    """Extract JSON object from text that may contain extra content."""
    # Find the first '{' and last '}'
    start = text.find('{')
    end = text.rfind('}')
    
    if start == -1 or end == -1 or start > end:
        raise ValueError(f"No valid JSON found in output: {text[:200]}")
    
    return text[start:end + 1]


def build_prompt(raw_text: str) -> str:
    """Build a prompt to parse raw resume text into structured JSON."""
    return f"""
Return ONLY valid JSON. No explanations.

{{
  "name": "",
  "experience": [
    {{
      "title": "",
      "company": "",
      "bullets": []
    }}
  ]
}}

Input:
{raw_text}
"""


def build_tailored_prompt(raw_text: str, job_description: str, config: dict) -> str:
    """
    Build a prompt to tailor resume for a specific job posting.
    
    Uses config as skeleton (max_bullets, max_jobs, etc.) but lets LLM
    apply intelligent reasoning on top of these rules.
    """
    max_bullets = config.get("max_bullets", 4)
    max_jobs = config.get("max_jobs", 5)
    max_skills = config.get("max_skills", 15)
    tailor_bullets = config.get("tailor_bullets", True)
    bullet_faithfulness = config.get("bullet_faithfulness", "high")
    include_projects = config.get("include_projects", False)
    projects_when_relevant = config.get("projects_when_relevant", True)
    
    tailoring_instructions = ""
    if tailor_bullets:
        if bullet_faithfulness == "high":
            tailoring_instructions += (
                "\n- Rewrite bullets to emphasize relevance to this job, "
                "but stay nearly identical to the original accomplishments."
            )
        else:
            tailoring_instructions += (
                "\n- Rewrite bullets to closely match the job requirements and keywords."
            )
    
    projects_note = ""
    if projects_when_relevant:
        projects_note = (
            "\n- If this job description strongly emphasizes projects/portfolio work, "
            "include a dedicated 'Projects' section with max 2 projects."
        )
    
    return f"""
You are an expert resume tailoring assistant. Parse and tailor the provided resume 
for the specific job posting below.

CONFIGURATION RULES (apply intelligently):
- Max bullets per job: {max_bullets}
- Max experience entries to include: {max_jobs}
- Max skills to list: {max_skills}
{tailoring_instructions}
{projects_note}

Return ONLY valid JSON. No explanations. Use this schema:

{{
  "name": "",
  "email": "",
  "phone": "",
  "linkedin": "",
  "github": "",
  "summary": "",
  "experience": [
    {{
      "title": "",
      "company": "",
      "location": "",
      "start_date": "",
      "end_date": "",
      "bullets": []
    }}
  ],
  "education": [
    {{
      "degree": "",
      "institution": "",
      "year": ""
    }}
  ],
  "skills": [],
  "projects": [
    {{
      "name": "",
      "description": "",
      "technologies": []
    }}
  ]
}}

RESUME TO TAILOR:
{raw_text}

JOB POSTING:
{job_description}

Tailor this resume for the job posting above. Use your judgment to:
1. Select the most relevant {max_jobs} experience entries
2. Reorder by relevance to the job
3. Trim/rewrite bullets to match job keywords and requirements
4. Select top {max_skills} most relevant skills
5. Include projects only if highly relevant to this role
"""
