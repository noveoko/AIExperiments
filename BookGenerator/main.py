import argparse
import requests
import subprocess
import os
import shutil
import tempfile
import re
from datetime import datetime
import json
from pathlib import Path
import sys

CACHE_DIR = Path("./.book_cache")
CACHE_DIR.mkdir(exist_ok=True)
MODEL = 'deepseek-r1:8b'

def get_cache_path(topic):
    safe_topic = "".join(c if c.isalnum() else "_" for c in topic)
    return CACHE_DIR / f"{safe_topic}_state.json"

def save_state(topic, subtopics, contents):
    state = {
        "subtopics": subtopics,
        "contents": contents,
        "version": 1
    }
    with open(get_cache_path(topic), 'w', encoding='utf-8') as f:
        json.dump(state, f, indent=2)

def load_state(topic):
    cache_file = get_cache_path(topic)
    if not cache_file.exists():
        return None
        
    try:
        with open(cache_file, 'r', encoding='utf-8') as f:
            state = json.load(f)
            if state.get("version") == 1:
                return state["subtopics"], state["contents"]
    except Exception as e:
        print(f"Error loading cache: {e}")
    return None

def validate_response(text, original_prompt):
    """Ensure response matches requirements"""
    if re.search(r'(think|monologue|self.reference|internal)', text, re.I):
        return False
    if len(text) < len(original_prompt) / 2:  # Minimum content check
        return False
    return True

def escape_latex(s):
    replacements = {
        # Keep existing replacements
        '’': "'",  # Replace smart apostrophes
        '“': r'``',
        '”': r"''",
        '–': r'--',
        '—': r'---',
        '\uff0c': ',',  # Replace full-width comma
        '‘': '`',
        # Add other Unicode replacements as needed
    }
    # Add existing replacements
    replacements.update({
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\^{}',
        '\\': r'\textbackslash{}',
        '<': r'\textless{}',
        '>': r'\textgreater{}',
    })
    
    for char, repl in replacements.items():
        s = s.replace(char, repl)
    # Remove any remaining non-ASCII characters
    s = s.encode('ascii', 'ignore').decode()
    return s

def clean_response(text):
    """Multi-stage cleaning process for model outputs"""
    # Remove LaTeX-escaped thinking blocks
    text = re.sub(
        r'\\textless{}think\\textgreater{}.*?\\textless{}/think\\textgreater{}', 
        '', 
        text, 
        flags=re.DOTALL|re.IGNORECASE
    )
    
    # Remove conversational patterns
    patterns = [
        r'^(Okay,? |So,? |First,? |Well,? |Hmm,? |Alright,? )',
        r'Let me (explain|start|begin|clarify)',
        r'(As an AI|I should|I need to|I\'ll)',
        r'\(\s*internal .*?\)',
        r'\[.*?thinking.*?\]',
        r'^[A-Za-z]+:\s*'  # Remove speaker labels
    ]
    
    for pattern in patterns:
        text = re.sub(pattern, '', text, flags=re.MULTILINE|re.IGNORECASE)
    
    # Split and filter lines for subtopics
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n'.join(
        line for line in lines 
        if len(line) > 12 
        and not line.startswith(('Okay', 'So ', 'First'))
        and not any(c in line for c in '{}<>[]()')
    )


def generate_text(prompt, model=MODEL, max_retries=9):
    """Enhanced text generation with validation"""
    system_prompt = (
        "IMPORTANT: You are a technical writer creating professional content. "
        "NEVER include:\n"
        "- Internal monologue\n"
        "- Thinking blocks\n"
        "- Self-references\n"
        "- Unfinished sentences\n"
        "- Placeholder text\n"
        "Format: Strict technical content only\n"
        "Style: Professional, direct, factual"
    )
    
    for attempt in range(max_retries):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": f"{system_prompt}\n\n{prompt}",
                    "stream": False,  # Explicitly disable streaming
                    "options": {
                        "temperature": 0.3 if attempt == 0 else 0.2,
                        "repeat_penalty": 2.0,
                        "num_ctx": 4096
                    }
                },
                timeout=30  # Add timeout
            )
            response.raise_for_status()  # Check HTTP status code
            
            # Handle possible empty response
            if not response.content:
                raise ValueError("Empty response from Ollama")
                
            response_data = response.json()
            
            # Validate JSON structure
            if "response" not in response_data:
                raise KeyError("Missing 'response' field in Ollama output")
                
        except (requests.exceptions.JSONDecodeError, 
                requests.exceptions.RequestException,
                KeyError) as e:
            print(f"API error: {str(e)}")
            if attempt == max_retries - 1:
                raise
            continue
                
        cleaned = clean_response(response_data["response"])
        if validate_response(cleaned, prompt):
            return cleaned
        print(f"Regenerating due to invalid content (attempt {attempt+1})")
    
    raise ValueError("Failed to generate valid content after multiple attempts")

def generate_subtopics(topic):
    prompt = f"""Generate 7-10 specific subtopics for "{topic}" using this template:
[Main Concept] - [Specific Aspect]
Examples:
- Network Forensics: Tracing Anonymous VPN Usage
- Social Media Analysis: Identifying Fake Profiles Patterns
- Dark Web Monitoring: Cryptocurrency Transaction Tracking

Format requirements:
- One subtopic per line
- No markdown
- No explanations
- Use colon separator for main concepts"""
    
    response = generate_text(prompt)
    return response.split('\n')[:10]

def generate_chapter_content(topic, subtopic):
    prompt = f"""Write technical content for '{subtopic}' in '{topic}'.
Include:
- LaTeX sections/subsections
- Practical examples
- Tool commands
- Recent data (2024-2025)
- Code blocks (if applicable)
Format:
\\section{{Section Title}}
Content with \\textbf{{bold terms}} and \\textit{{explanations}}.
\\subsection{{Subsection Title}}
Bullet points:
\\begin{{itemize}}
\\item First point
\\item Second point
\\end{{itemize}}"""
    
    return generate_text(prompt)

def build_latex_document(topic, subtopics, contents):
    latex = f"""\\documentclass{{book}}
\\usepackage[utf8]{{inputenc}}
\\usepackage[T1]{{fontenc}}
\\usepackage{{hyperref}}
\\usepackage{{listings}}
\\usepackage{{xunicode}}  % Add this line
\\title{{{escape_latex(topic)}}}
\\author{{OSINT Security Expert}}
\\date{{\\today}}

\\begin{{document}}
\\maketitle
\\tableofcontents
"""

def main():
    parser = argparse.ArgumentParser(description="Generate an ebook using Ollama")
    parser.add_argument("topic", help="Main topic of the ebook")
    parser.add_argument("--resume", action="store_true", help="Continue from last saved state")
    args = parser.parse_args()

    if not shutil.which('pdflatex'):
        print("Error: pdflatex not found. Please install TeX Live or MiKTeX.")
        return

    # Load existing state
    subtopics = []
    contents = []
    if args.resume or load_state(args.topic):
        existing = load_state(args.topic)
        if existing:
            subtopics, contents = existing
            print(f"Resuming generation ({len(contents)}/{len(subtopics)} chapters done)")
            if input("Continue? (y/n): ").lower() == 'y':
                # Remove potentially corrupted last entry
                contents = contents[:-1] if len(contents) == len(subtopics) else contents
            else:
                subtopics = []
                contents = []

    if not subtopics:
        print(f"Generating ebook outline for '{args.topic}'...")
        subtopics = generate_subtopics(args.topic)
        print(f"Generated {len(subtopics)} subtopics")
        save_state(args.topic, subtopics, [])

    try:
        for i in range(len(contents), len(subtopics)):
            subtopic = subtopics[i]
            print(f"Generating chapter {i+1}/{len(subtopics)}: {subtopic}")
            content = generate_chapter_content(args.topic, subtopic)
            contents.append(content)
            save_state(args.topic, subtopics, contents)  # Save after each chapter

        print("Compiling LaTeX document...")
        latex_document = build_latex_document(args.topic, subtopics, contents)

        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = os.path.join(tmpdir, "ebook.tex")
            with open(tex_path, 'w', encoding='utf-8') as f:
                f.write(latex_document)

            try:
                for _ in range(2):  # Run twice to generate TOC
                    result = subprocess.run(
                        ["pdflatex", "-interaction=nonstopmode", tex_path],
                        cwd=tmpdir,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode != 0:
                        print("LaTeX compilation error:")
                        print(result.stderr)
                        return
            except Exception as e:
                print(f"Error running pdflatex: {e}")
                return

            pdf_path = os.path.join(tmpdir, "ebook.pdf")
            if os.path.exists(pdf_path):
                output_pdf = f"{args.topic.replace(' ', '_')}_ebook.pdf"
                shutil.copy(pdf_path, output_pdf)
                print(f"\nSuccessfully generated ebook: {output_pdf}")
                # Clear cache on success
                get_cache_path(args.topic).unlink(missing_ok=True)
            else:
                print("PDF generation failed - state preserved for resume")

    except Exception as e:
        print(f"\nERROR: {str(e)}")
        print("Progress saved. Resume later with:")
        print(f"python {sys.argv[0]} '{args.topic}' --resume")
        save_state(args.topic, subtopics, contents)

if __name__ == "__main__":
    main()
