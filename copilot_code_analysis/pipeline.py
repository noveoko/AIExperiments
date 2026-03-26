#!/usr/bin/env python3
"""
pipeline.py — Code Review Pipeline using Microsoft Copilot browser automation.

Workflow (step-by-step):
  1. Accept a target directory as a CLI argument.
  2. Discover all .gitignore files in that directory tree and build a
     pathspec matcher so ignored files are skipped.
  3. Walk the directory and collect every .py file that isn't ignored.
  4. For each Python file, pass its absolute path to copilot_analyzer.js.
     The Node script uploads the file as an ATTACHMENT in Copilot's UI —
     the code is never pasted into the chat textarea, so there is no
     16,000-character input limit to worry about.
  5. Parse the returned JSON (list of 5–10 improvements per file).
  6. Accumulate results and write a final report (JSON + human-readable summary).

Usage:
    python pipeline.py /path/to/your/project
    python pipeline.py /path/to/your/project --output report.json --verbose
    python pipeline.py /path/to/your/project --dry-run   # just list files
"""

import argparse
import json
import os
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── Dependency check ──────────────────────────────────────────────────────────
try:
    import pathspec
except ImportError:
    print(
        "Error: 'pathspec' is not installed.\n"
        "Fix: pip install pathspec",
        file=sys.stderr,
    )
    sys.exit(1)

# ── Constants ──────────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
ANALYZER_SCRIPT = SCRIPT_DIR / "copilot_analyzer.js"

# Exit codes returned by copilot_analyzer.js (must stay in sync with JS file)
EXIT_OK = 0
EXIT_AUTH_FAILURE = 2
EXIT_UPLOAD_FAILED = 3

# How long (seconds) to wait for Copilot to respond per file
ANALYZER_TIMEOUT = 240

# Directories to always skip regardless of .gitignore
ALWAYS_SKIP_DIRS = {
    ".git", ".hg", ".svn",         # VCS internals
    "__pycache__", ".mypy_cache",  # Python caches
    ".venv", "venv", "env",        # virtual environments
    "node_modules",                # JS deps
    ".tox", ".nox",                # test runners
    "dist", "build", "*.egg-info", # build artefacts
    ".eggs",
}


# ─────────────────────────────────────────────────────────────────────────────
# Step 1 – .gitignore discovery and parsing
# ─────────────────────────────────────────────────────────────────────────────

def load_gitignore_spec(directory: Path) -> Optional[pathspec.PathSpec]:
    """
    Walk from `directory` up to the git root, collecting all .gitignore
    patterns along the way, and return a compiled PathSpec matcher.

    Why walk upward?  A project may have a root .gitignore and also
    sub-directory .gitignore files — pathspec needs all of them.
    """
    patterns: list[str] = []

    current = directory
    while True:
        gitignore_file = current / ".gitignore"
        if gitignore_file.is_file():
            try:
                raw = gitignore_file.read_text(encoding="utf-8", errors="replace")
                patterns.extend(raw.splitlines())
            except OSError as exc:
                print(f"[WARN] Could not read {gitignore_file}: {exc}", file=sys.stderr)

        # Stop at the git root (presence of .git directory)
        if (current / ".git").is_dir():
            break

        parent = current.parent
        if parent == current:  # filesystem root reached
            break
        current = parent

    if not patterns:
        return None

    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


# ─────────────────────────────────────────────────────────────────────────────
# Step 2 – Python file discovery
# ─────────────────────────────────────────────────────────────────────────────

def find_python_files(
    directory: Path,
    spec: Optional[pathspec.PathSpec],
) -> list[Path]:
    """
    Recursively collect all .py files under `directory`, skipping:
      • Hidden directories (starting with '.')
      • Entries in ALWAYS_SKIP_DIRS
      • Paths matched by the gitignore PathSpec

    Returns a sorted list of absolute Path objects.
    """
    found: list[Path] = []

    for root, dirs, files in os.walk(directory, topdown=True):
        root_path = Path(root)
        rel_root = root_path.relative_to(directory)

        # ── Prune directories in-place so os.walk won't descend ──────────────
        def should_skip_dir(d: str) -> bool:
            if d.startswith("."):
                return True
            if d in ALWAYS_SKIP_DIRS:
                return True
            if spec:
                rel = str(rel_root / d)
                # pathspec expects trailing slash for directories
                if spec.match_file(rel + "/") or spec.match_file(rel):
                    return True
            return False

        dirs[:] = [d for d in dirs if not should_skip_dir(d)]

        # ── Collect Python files ──────────────────────────────────────────────
        for filename in files:
            if not filename.endswith(".py"):
                continue
            rel_path = str(rel_root / filename)
            if spec and spec.match_file(rel_path):
                continue  # gitignore matched
            found.append(root_path / filename)

    return sorted(found)


# ─────────────────────────────────────────────────────────────────────────────
# Step 3 – Per-file analysis (calls copilot_analyzer.js)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_file(filepath: Path) -> dict:
    """
    Pass `filepath` to copilot_analyzer.js and return the parsed JSON result.

    The Node script uploads the file as a UI attachment — the source code is
    NEVER read or piped through this process. This sidesteps the ~16,000-
    character textarea limit that would make pasting large files impossible.

    The Node script:
      • Receives the absolute file path as argv[2]
      • Uploads the file via Playwright's setInputFiles() / fileChooser API
      • Writes structured JSON to stdout
      • Writes all debug/progress info to stderr (relayed below)

    Raises RuntimeError for known failure modes (auth failure, timeout).
    """
    result = subprocess.run(
        ["node", str(ANALYZER_SCRIPT), str(filepath.resolve())],
        capture_output=True,
        text=True,
        timeout=ANALYZER_TIMEOUT,
        encoding="utf-8",
    )

    # Relay Node's stderr (INFO/WARN messages) to our stderr, indented
    if result.stderr.strip():
        for line in result.stderr.splitlines():
            print(f"  {line}", file=sys.stderr)

    # ── Handle known exit codes ───────────────────────────────────────────────
    if result.returncode == EXIT_AUTH_FAILURE:
        raise RuntimeError(
            "AUTHENTICATION FAILURE — Copilot session has expired. "
            "Re-run  node setup_session.js  to refresh state.json."
        )
    if result.returncode == EXIT_UPLOAD_FAILED:
        raise RuntimeError(
            "FILE UPLOAD FAILED — Playwright could not attach the file to "
            "Copilot's UI. The attachment button selectors may need updating."
        )
    if result.returncode != EXIT_OK:
        raise RuntimeError(
            f"Analyzer exited with code {result.returncode}. "
            f"stderr tail: {result.stderr[-400:]!r}"
        )

    if not result.stdout.strip():
        raise RuntimeError("Analyzer produced no stdout output.")

    return json.loads(result.stdout)


# ─────────────────────────────────────────────────────────────────────────────
# Step 4 – Human-readable summary writer
# ─────────────────────────────────────────────────────────────────────────────

def print_summary(report: dict, directory: Path) -> None:
    """Print a nicely formatted summary to stdout."""
    summary = report["summary"]
    results = report["results"]
    errors = report["errors"]

    width = 70
    print("=" * width)
    print("  COPILOT CODE REVIEW — RESULTS SUMMARY")
    print("=" * width)
    print(f"  Directory : {directory}")
    print(f"  Scanned   : {summary['total_files']} Python file(s)")
    print(f"  Analysed  : {summary['files_analyzed']} successfully")
    print(f"  Failed    : {summary['files_failed']}")
    print(f"  Run at    : {summary['timestamp']}")
    print("=" * width)

    for i, entry in enumerate(results, 1):
        rel = Path(entry["file"]).relative_to(directory) if Path(entry["file"]).is_absolute() else entry["file"]
        print(f"\n{'─' * width}")
        print(f"  [{i}] {rel}")
        print(f"{'─' * width}")
        improvements = entry.get("improvements", [])
        if improvements:
            for j, imp in enumerate(improvements, 1):
                # Word-wrap long lines at 65 chars, indent continuation
                wrapped = textwrap.fill(
                    imp,
                    width=65,
                    initial_indent=f"  {j:>2}. ",
                    subsequent_indent="      ",
                )
                print(wrapped)
        else:
            print("  (No structured improvements extracted — see raw_response in JSON)")

    if errors:
        print(f"\n{'─' * width}")
        print("  ERRORS")
        print(f"{'─' * width}")
        for e in errors:
            print(f"  ✗ {e['file']}")
            print(f"    {e['error']}")

    print(f"\n{'=' * width}\n")


# ─────────────────────────────────────────────────────────────────────────────
# Step 5 – Pre-flight checks
# ─────────────────────────────────────────────────────────────────────────────

def preflight_check() -> None:
    """Verify all external dependencies are available before starting."""
    # Check Node.js
    try:
        node_result = subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        )
        if node_result.returncode != 0:
            raise RuntimeError("node exited non-zero")
        print(f"[✓] Node.js {node_result.stdout.strip()}", file=sys.stderr)
    except (FileNotFoundError, RuntimeError):
        print(
            "[✗] Node.js not found. Install from https://nodejs.org/",
            file=sys.stderr,
        )
        sys.exit(1)

    # Check copilot_analyzer.js exists
    if not ANALYZER_SCRIPT.is_file():
        print(
            f"[✗] Analyzer script not found: {ANALYZER_SCRIPT}",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[✓] Analyzer script: {ANALYZER_SCRIPT}", file=sys.stderr)

    # Check node_modules are installed
    nm = SCRIPT_DIR / "node_modules"
    if not nm.is_dir():
        print(
            "[✗] node_modules not found. Run  npm install  in the project directory.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[✓] node_modules present", file=sys.stderr)

    # Check state.json exists
    state_file = SCRIPT_DIR / "state.json"
    if not state_file.is_file():
        print(
            "[✗] state.json not found. Run  node setup_session.js  first.",
            file=sys.stderr,
        )
        sys.exit(1)
    print(f"[✓] Session state: {state_file}", file=sys.stderr)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze Python files in a directory using Microsoft Copilot "
            "browser automation. Respects .gitignore rules."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              python pipeline.py ./my_project
              python pipeline.py ./my_project --output report.json --verbose
              python pipeline.py ./my_project --dry-run
        """),
    )
    parser.add_argument(
        "directory",
        help="Root directory to scan for Python files",
    )
    parser.add_argument(
        "--output", "-o",
        metavar="FILE",
        help="Write the full JSON report to FILE (default: also printed to stdout)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Print each improvement to stderr as files are processed",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Discover and list Python files but do NOT call Copilot",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip dependency checks (useful if you know the env is set up)",
    )
    args = parser.parse_args()

    # ── Resolve directory ─────────────────────────────────────────────────────
    directory = Path(args.directory).resolve()
    if not directory.is_dir():
        print(f"Error: '{directory}' is not a directory.", file=sys.stderr)
        sys.exit(1)

    print(f"\n[*] Target directory : {directory}", file=sys.stderr)

    # ── Pre-flight checks ─────────────────────────────────────────────────────
    if not args.skip_preflight and not args.dry_run:
        print("[*] Running pre-flight checks…", file=sys.stderr)
        preflight_check()

    # ── Step 1: Load .gitignore ───────────────────────────────────────────────
    print("[*] Loading .gitignore rules…", file=sys.stderr)
    spec = load_gitignore_spec(directory)
    if spec:
        print(f"[✓] .gitignore rules loaded", file=sys.stderr)
    else:
        print("[!] No .gitignore found (no files will be excluded by gitignore)", file=sys.stderr)

    # ── Step 2: Discover Python files ─────────────────────────────────────────
    print("[*] Discovering Python files…", file=sys.stderr)
    py_files = find_python_files(directory, spec)
    print(f"[✓] Found {len(py_files)} Python file(s)", file=sys.stderr)

    if not py_files:
        print("No Python files found in the specified directory.", file=sys.stderr)
        sys.exit(0)

    # ── Dry-run: just list files ───────────────────────────────────────────────
    if args.dry_run:
        print("\nFiles that would be analyzed (dry-run mode):")
        for f in py_files:
            print(f"  {f.relative_to(directory)}")
        print(f"\nTotal: {len(py_files)} file(s)")
        return

    # ── Step 3 & 4: Analyze each file ─────────────────────────────────────────
    results: list[dict] = []
    errors: list[dict] = []
    auth_failure = False

    for i, filepath in enumerate(py_files, 1):
        rel = filepath.relative_to(directory)
        print(f"\n[{i}/{len(py_files)}] Analyzing: {rel}", file=sys.stderr)

        try:
            result = analyze_file(filepath)
            results.append(result)

            n = len(result.get("improvements", []))
            print(f"  → {n} improvement(s) found", file=sys.stderr)

            if args.verbose:
                for j, imp in enumerate(result.get("improvements", []), 1):
                    print(f"     {j}. {imp}", file=sys.stderr)

        except subprocess.TimeoutExpired:
            msg = f"Timed out after {ANALYZER_TIMEOUT}s"
            print(f"  ✗ {msg}", file=sys.stderr)
            errors.append({"file": str(rel), "error": msg})

        except RuntimeError as exc:
            msg = str(exc)
            print(f"  ✗ {msg}", file=sys.stderr)
            errors.append({"file": str(rel), "error": msg})

            # Auth failures are fatal — no point continuing
            if "AUTHENTICATION FAILURE" in msg:
                auth_failure = True
                break

        except json.JSONDecodeError as exc:
            msg = f"Failed to parse analyzer output as JSON: {exc}"
            print(f"  ✗ {msg}", file=sys.stderr)
            errors.append({"file": str(rel), "error": msg})

    # ── Step 5: Assemble and output report ────────────────────────────────────
    report = {
        "summary": {
            "directory": str(directory),
            "total_files": len(py_files),
            "files_analyzed": len(results),
            "files_failed": len(errors),
            "auth_failure_detected": auth_failure,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "results": results,
        "errors": errors,
    }

    report_json = json.dumps(report, indent=2, ensure_ascii=False)

    # Always write JSON report
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(report_json, encoding="utf-8")
        print(f"\n[✓] JSON report saved → {output_path}", file=sys.stderr)

    # Print human-readable summary to stdout
    print_summary(report, directory)

    # Also print JSON to stdout if no output file specified
    if not args.output:
        print(report_json)

    # Exit non-zero if anything failed
    if auth_failure:
        print(
            "\n[!] Pipeline stopped early due to auth failure.\n"
            "    Run  node setup_session.js  to refresh your session.",
            file=sys.stderr,
        )
        sys.exit(EXIT_AUTH_FAILURE)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
