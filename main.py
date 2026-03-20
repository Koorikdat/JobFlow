import json
import yaml
import subprocess
import sys
import argparse
import os
import re
from pathlib import Path
from jinja2 import Template
from resume.llm import call_llm, build_prompt, build_tailored_prompt


def sanitize_filename(s: str) -> str:
    """Remove/replace invalid filename characters."""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', s).lower()


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Resume generation and tailoring")
    parser.add_argument("--job", type=str, help="Job posting text or description")
    parser.add_argument("--company", type=str, help="Company name (for output filename)")
    parser.add_argument("--role", type=str, help="Job role/title (for output filename)")
    parser.add_argument("--input", type=str, default="data/input.txt", help="Path to resume input file")
    parser.add_argument("--config", type=str, default="config/default.yaml", help="Path to config file")
    parser.add_argument("--output-dir", type=str, default="output", help="Output directory")
    
    args = parser.parse_args()
    
    # Create output directory
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 1. Load input resume
    with open(args.input) as f:
        raw_text = f.read()
    
    # 2. Load config
    with open(args.config) as f:
        config = yaml.safe_load(f)
    
    # 3. Call LLM (tailored or generic)
    if args.job:
        print("Tailoring resume for job posting...")
        prompt = build_tailored_prompt(raw_text, args.job, config)
    else:
        print("Parsing resume to structured format...")
        prompt = build_prompt(raw_text)
    
    data = call_llm(prompt)
    
    # 4. Apply config limits
    max_bullets = config.get("max_bullets", 3)
    for job in data.get("experience", []):
        job["bullets"] = job["bullets"][:max_bullets]
    
    # 5. Load and render template
    template_path = "resume/templates/resume.tex.j2"
    with open(template_path) as f:
        template = Template(f.read())
    
    latex = template.render(**data)
    
    # 6. Determine output filename
    if args.job and args.company and args.role:
        safe_company = sanitize_filename(args.company)
        safe_role = sanitize_filename(args.role)
        output_name = f"{safe_company}_{safe_role}_resume"
    else:
        output_name = "resume"
    
    tex_path = os.path.join(args.output_dir, f"{output_name}.tex")
    pdf_path = os.path.join(args.output_dir, f"{output_name}.pdf")
    
    # 7. Write .tex file
    with open(tex_path, "w") as f:
        f.write(latex)
    
    print(f"Wrote LaTeX to {tex_path}")
    
    # 8. Compile PDF
    subprocess.run([
        "pdflatex",
        "-output-directory=" + args.output_dir,
        tex_path
    ], capture_output=True)
    
    print(f"Generated PDF → {pdf_path}")


if __name__ == "__main__":
    main()