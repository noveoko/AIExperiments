import argparse
import requests
import subprocess
import re
import json
from datetime import datetime
from pathlib import Path
import sys
from typing import List, Dict, Tuple, Optional
import tempfile
import shutil


class Config:
    """Central configuration class"""
    CACHE_DIR = Path("./.book_cache")
    DEFAULT_MODEL = 'deepseek-r1:8b'
    MAX_RETRIES = 3
    LATEX_COMPILE_ATTEMPTS = 2
    MIN_CONTENT_RATIO = 0.5


class StateManager:
    """Handles saving/loading generation state"""
    def __init__(self, topic: str):
        self.topic = topic
        self.cache_path = self._get_cache_path()
        Config.CACHE_DIR.mkdir(exist_ok=True)

    def _get_cache_path(self) -> Path:
        safe_topic = re.sub(r'[^\w]', '_', self.topic)
        return Config.CACHE_DIR / f"{safe_topic}_state.json"

    def save(self, subtopics: List[str], contents: List[str]) -> None:
        """Save current generation state"""
        state = {
            "subtopics": subtopics,
            "contents": contents,
            "version": 2,
            "timestamp": datetime.now().isoformat()
        }
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(state, f, indent=2)

    def load(self) -> Optional[Tuple[List[str], List[str]]]:
        """Load previous generation state"""
        if not self.cache_path.exists():
            return None

        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                state = json.load(f)
                if state.get("version") == 2:
                    return state["subtopics"], state["contents"]
        except Exception as e:
            print(f"Error loading state: {e}")
        return None

    def clear(self) -> None:
        """Remove cached state"""
        self.cache_path.unlink(missing_ok=True)


class APIClient:
    """Handles communication with Ollama API"""
    def __init__(self, model: str = Config.DEFAULT_MODEL):
        self.base_url = "http://localhost:11434/api/generate"
        self.model = model
        self.timeout = 30

    def generate_text(self, prompt: str, system_prompt: str) -> str:
        """Generate text with validation and retries"""
        for attempt in range(Config.MAX_RETRIES):
            try:
                response = self._make_api_call(prompt, system_prompt, attempt)
                return self._process_response(response, prompt)
            except (requests.RequestException, json.JSONDecodeError) as e:
                if attempt == Config.MAX_RETRIES - 1:
                    raise RuntimeError(f"API request failed: {e}") from e

        raise RuntimeError("Max retries exceeded without success")

    def _make_api_call(self, prompt: str, system_prompt: str, attempt: int) -> requests.Response:
        """Execute the API call"""
        return requests.post(
            self.base_url,
            json={
                "model": self.model,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.3 - (0.1 * attempt),
                    "repeat_penalty": 2.0,
                    "num_ctx": 4096
                }
            },
            timeout=self.timeout
        )

    def _process_response(self, response: requests.Response, original_prompt: str) -> str:
        """Validate and process API response"""
        response.raise_for_status()
        response_data = response.json()
        
        if "response" not in response_data:
            raise ValueError("Invalid API response format")

        cleaned = ContentProcessor.clean_response(response_data["response"])
        if ContentProcessor.is_valid(cleaned, original_prompt):
            return cleaned
            
        raise ValueError("Generated content failed validation")


class ContentProcessor:
    """Handles content cleaning and validation"""
    LATE_REPLACEMENTS = {
        '’': "'", '“': r'``', '”': r"''", '–': r'--', '—': r'---',
        '\uff0c': ',', '‘': '`', '&': r'\&', '%': r'\%', '$': r'\$',
        '#': r'\#', '_': r'\_', '{': r'\{', '}': r'\}', '~': r'\textasciitilde{}',
        '^': r'\^{}', '\\': r'\textbackslash{}', '<': r'\textless{}', '>': r'\textgreater{}'
    }

    @classmethod
    def clean_response(cls, text: str) -> str:
        """Multi-stage cleaning process for model outputs"""
        text = cls._remove_thinking_blocks(text)
        text = cls._remove_conversational_patterns(text)
        return cls._filter_lines(text)

    @classmethod
    def is_valid(cls, text: str, original_prompt: str) -> bool:
        """Validate generated content meets requirements"""
        if re.search(r'(think|monologue|self.reference|internal)', text, re.I):
            return False
        if len(text) < len(original_prompt) * Config.MIN_CONTENT_RATIO:
            return False
        return True

    @staticmethod
    def _remove_thinking_blocks(text: str) -> str:
        return re.sub(
            r'\\textless{}think\\textgreater{}.*?\\textless{}/think\\textgreater{}',
            '',
            text,
            flags=re.DOTALL|re.IGNORECASE
        )

    @staticmethod
    def _remove_conversational_patterns(text: str) -> str:
        patterns = [
            r'^(Okay,? |So,? |First,? |Well,? |Hmm,? |Alright,? )',
            r'Let me (explain|start|begin|clarify)',
            r'(As an AI|I should|I need to|I\'ll)',
            r'\(\s*internal .*?\)',
            r'\[.*?thinking.*?\]',
            r'^[A-Za-z]+:\s*'  # Speaker labels
        ]
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE|re.IGNORECASE)
        return text

    @staticmethod
    def _filter_lines(text: str) -> str:
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        return '\n'.join(
            line for line in lines 
            if len(line) > 12 
            and not line.startswith(('Okay', 'So ', 'First'))
            and not any(c in line for c in '{}<>[]()')
        )

    @classmethod
    def escape_latex(cls, text: str) -> str:
        """Sanitize text for LaTeX inclusion"""
        for char, repl in cls.LATE_REPLACEMENTS.items():
            text = text.replace(char, repl)
        return text.encode('ascii', 'ignore').decode()


class LatexBuilder:
    """Handles LaTeX document construction"""
    TEMPLATE = r"""\documentclass{{book}}
\usepackage[utf8]{{inputenc}}
\usepackage[T1]{{fontenc}}
\usepackage{{hyperref}}
\usepackage{{listings}}
\usepackage{{xcolor}}
\usepackage{{xunicode}}

\title{{{title}}}
\author{{OSINT Security Expert}}
\date{{\today}}

\begin{{document}}
\maketitle
\tableofcontents

{content}

\end{{document}}
"""

    @classmethod
    def build_document(cls, topic: str, subtopics: List[str], contents: List[str]) -> str:
        """Construct complete LaTeX document"""
        escaped_topic = ContentProcessor.escape_latex(topic)
        content_sections = []
        
        for subtitle, content in zip(subtopics, contents):
            section = cls._build_section(subtitle, content)
            content_sections.append(section)

        return cls.TEMPLATE.format(
            title=escaped_topic,
            content='\n'.join(content_sections)
        )

    @staticmethod
    def _build_section(subtitle: str, content: str) -> str:
        escaped_subtitle = ContentProcessor.escape_latex(subtitle)
        return f"\\chapter{{{escaped_subtitle}}}\n{content}\n"


class EbookGenerator:
    """Orchestrates ebook generation process"""
    def __init__(self, topic: str):
        self.topic = topic
        self.state_manager = StateManager(topic)
        self.api_client = APIClient()
        self.subtopics: List[str] = []
        self.contents: List[str] = []

    def generate(self, resume: bool = False) -> None:
        """Main generation workflow"""
        self._load_state(resume)
        self._generate_missing_content()
        self._compile_latex()

    def _load_state(self, resume: bool) -> None:
        """Load existing state or generate new outline"""
        if resume:
            state = self.state_manager.load()
            if state:
                self.subtopics, self.contents = state
                print(f"Resuming with {len(self.contents)}/{len(self.subtopics)} chapters")
                if input("Continue? (y/n): ").lower() != 'y':
                    self.subtopics, self.contents = [], []

        if not self.subtopics:
            self.subtopics = self._generate_subtopics()
            self.state_manager.save(self.subtopics, self.contents)

    def _generate_subtopics(self) -> List[str]:
        """Generate chapter outline"""
        prompt = f"""Generate 7-10 specific subtopics for "{self.topic}" using:
[Main Concept] - [Specific Aspect] format with colon separators"""
        system_prompt = self._get_system_prompt("outline")
        response = self.api_client.generate_text(prompt, system_prompt)
        return response.split('\n')[:10]

    def _generate_missing_content(self) -> None:
        """Generate missing chapter content"""
        for idx in range(len(self.contents), len(self.subtopics)):
            self._generate_chapter(idx)

    def _generate_chapter(self, index: int) -> None:
        """Generate single chapter and save state"""
        subtopic = self.subtopics[index]
        print(f"Generating chapter {index+1}/{len(self.subtopics)}: {subtopic}")
        
        prompt = f"Write technical content for '{subtopic}' in '{self.topic}'"
        system_prompt = self._get_system_prompt("chapter")
        content = self.api_client.generate_text(prompt, system_prompt)
        
        self.contents.append(content)
        self.state_manager.save(self.subtopics, self.contents)

    @staticmethod
    def _get_system_prompt(content_type: str) -> str:
        """Get appropriate system prompt"""
        prompts = {
            "outline": "You are a technical writer creating a book outline. ",
            "chapter": "You are a security expert writing detailed technical content. "
        }
        base = (
            "Format: Strict technical content only\n"
            "Style: Professional, direct, factual\n"
            "Prohibited: Internal monologue, thinking blocks, self-references"
        )
        return prompts.get(content_type, "") + base

    def _compile_latex(self) -> None:
        """Compile LaTeX document to PDF"""
        latex_content = LatexBuilder.build_document(self.topic, self.subtopics, self.contents)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_path = Path(tmpdir) / "ebook.tex"
            tex_path.write_text(latex_content, encoding='utf-8')

            self._run_pdflatex(tmpdir, tex_path)
            self._handle_output(tmpdir)

    def _run_pdflatex(self, tmpdir: str, tex_path: Path) -> None:
        """Execute LaTeX compilation"""
        try:
            for _ in range(Config.LATEX_COMPILE_ATTEMPTS):
                result = subprocess.run(
                    ["pdflatex", "-interaction=nonstopmode", tex_path.name],
                    cwd=tmpdir,
                    capture_output=True,
                    text=True,
                    check=True
                )
                if "Error" in result.stderr:
                    raise RuntimeError(f"LaTeX error: {result.stderr}")
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"pdflatex failed: {e.stderr}") from e

    def _handle_output(self, tmpdir: str) -> None:
        """Handle final PDF output"""
        pdf_path = Path(tmpdir) / "ebook.pdf"
        if pdf_path.exists():
            output_name = f"{self.topic.replace(' ', '_')}_ebook.pdf"
            shutil.copy(pdf_path, output_name)
            print(f"\nSuccessfully generated ebook: {output_name}")
            self.state_manager.clear()
        else:
            raise FileNotFoundError("PDF output not found after compilation")


def main():
    """Command-line interface"""
    parser = argparse.ArgumentParser(description="Generate technical ebooks")
    parser.add_argument("topic", help="Main topic of the ebook")
    parser.add_argument("--resume", action="store_true", help="Continue previous generation")
    args = parser.parse_args()

    if not shutil.which('pdflatex'):
        sys.exit("Error: pdflatex required. Install TeX Live or MiKTeX.")

    try:
        generator = EbookGenerator(args.topic)
        generator.generate(resume=args.resume)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
