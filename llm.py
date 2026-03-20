import subprocess
import json

#active_model = "llama3.2:1b"
active_model = "mistral:7b-instruct"

def call_llm(prompt: str) -> dict:
    result = subprocess.run(
        ["ollama", "run", active_model],
        input=prompt,
        text=True,
        capture_output=True
    )

    output = result.stdout.strip()

    return json.loads(output)


def build_prompt(raw_text: str) -> str:
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