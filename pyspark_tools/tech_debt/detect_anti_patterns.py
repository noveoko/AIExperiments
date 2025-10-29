import os
import re
from typing import List, Dict, Any

# --- Configuration ---
# Folders to completely ignore during the repository scan
EXCLUDE_DIRS = ['venv', '.git', '__pycache__', 'build', 'dist', 'docs', 'tests', 'node_modules']
# File extensions to scan
FILE_EXTENSIONS = ['.py']

# --- Anti-Patterns Definitions ---
# The dictionary keys are the pattern IDs, and the values are the detection rules.
# Each rule contains:
# - 'description': A human-readable description of the anti-pattern.
# - 'type': 'pyspark' or 'python'.
# - 'pattern': A regular expression to search for.

ANTI_PATTERNS = {
    # PySpark Anti-Patterns (Performance & Robustness)
    'PS001': {
        'description': "Use of `.collect()` or `.toPandas()` without limits. This loads all data to the driver, potentially crashing the application.",
        'type': 'pyspark',
        'pattern': r'(df|spark|data)\s*\.(collect|toPandas)\s*\(\s*\)',
    },
    'PS002': {
        'description': "Non-explicit Schema Definition (inferSchema=True). Inferring schema requires an extra pass over the data, which is slow and error-prone.",
        'type': 'pyspark',
        'pattern': r'inferSchema\s*=\s*True',
    },
    'PS003': {
        'description': "Use of User Defined Functions (UDFs) without Arrow/Pandas UDFs. Standard UDFs are slow because they serialize data row-by-row.",
        'type': 'pyspark',
        # Simple detection: checks for standard UDF registration/usage
        'pattern': r'from\s+pyspark\.sql\.functions\s+import\s+udf',
    },
    'PS004': {
        'description': "Repartitioning to a very low number or 1. This can cause data skew and unnecessary shuffle costs.",
        'type': 'pyspark',
        # Checks for .repartition(1) or .coalesce(1)
        'pattern': r'\.(repartition|coalesce)\s*\(\s*1\s*\)',
    },
    'PS005': {
        'description': "Use of `.count()`. Calling count forces an action/shuffle and often isn't needed unless for logging.",
        'type': 'pyspark',
        'pattern': r'\.count\s*\(\s*\)',
    },

    # General Python Anti-Patterns (Maintainability & Safety)
    'PY001': {
        'description': "Wildcard imports (`from module import *`). This pollutes the namespace and makes code hard to trace.",
        'type': 'python',
        'pattern': r'from\s+.*\s+import\s+\*',
    },
    'PY002': {
        'description': "Mutable default arguments in function definitions (e.g., `def func(a=[]):`). This leads to shared state across calls.",
        'type': 'python',
        'pattern': r'def\s+\w+\s*\(.*=\s*(\[\]|\{\}|\w+\.acquire\(\))\s*\):',
    },
    'PY003': {
        'description': "Use of a bare `except:`. This catches all exceptions (including SystemExit, KeyboardInterrupt) and hides bugs.",
        'type': 'python',
        'pattern': r'^\s*except\s*:\s*$',
    },
    'PY004': {
        'description': "Unnecessarily verbose string formatting using `%` instead of f-strings or `.format()`.",
        'type': 'python',
        # Looks for the use of % operator for string interpolation
        'pattern': r'["\'].*?%[dsif].*?["\'].*?%',
    },
    'PY005': {
        'description': "Directly accessing private members (leading underscore). This indicates tight coupling.",
        'type': 'python',
        'pattern': r'\.\s*_[a-zA-Z_]\w*',
    },
}

# --- Core Logic ---

def is_excluded(path: str) -> bool:
    """Checks if a path or any of its parent directories should be excluded."""
    # Check if any part of the path matches an exclusion directory
    path_parts = path.split(os.sep)
    return any(part in EXCLUDE_DIRS for part in path_parts)

def scan_file_for_patterns(filepath: str) -> List[Dict[str, Any]]:
    """Scans a single file for all defined anti-patterns."""
    found_patterns = []
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        for line_num, line in enumerate(lines, 1):
            for pattern_id, rule in ANTI_PATTERNS.items():
                # Perform the search
                match = re.search(rule['pattern'], line)

                if match:
                    found_patterns.append({
                        'id': pattern_id,
                        'line': line_num,
                        'code_snippet': line.strip(),
                        'description': rule['description'],
                        'type': rule['type'],
                    })
        return found_patterns

    except UnicodeDecodeError:
        print(f"Skipping file due to encoding issue: {filepath}")
        return []
    except Exception as e:
        print(f"An error occurred while reading {filepath}: {e}")
        return []

def scan_repository(root_dir: str) -> Dict[str, List[Dict[str, Any]]]:
    """Traverses the repository and scans all relevant files."""
    report_data = {}
    print(f"Starting repository scan from: {os.path.abspath(root_dir)}")

    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=True):
        # Modify dirnames in place to skip excluded directories in the traversal
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE_DIRS]

        if is_excluded(dirpath):
            continue

        for filename in filenames:
            if any(filename.endswith(ext) for ext in FILE_EXTENSIONS):
                filepath = os.path.join(dirpath, filename)
                
                # Check exclusion again for the full path (just in case)
                if not is_excluded(filepath):
                    print(f"Scanning {filepath}...")
                    results = scan_file_for_patterns(filepath)
                    if results:
                        report_data[filepath] = results

    return report_data

def generate_report(report_data: Dict[str, List[Dict[str, Any]]]):
    """Formats and prints the anti-pattern report."""
    total_violations = sum(len(violations) for violations in report_data.values())
    
    if total_violations == 0:
        print("\n=======================================================")
        print("✅ SUCCESS: No PySpark or Python anti-patterns detected!")
        print("=======================================================")
        return

    print("\n=======================================================")
    print(f"🚨 ANTI-PATTERN SCAN REPORT: {total_violations} Violations Found")
    print("=======================================================\n")

    # Group by Pattern ID for summary
    violation_summary = {}
    for filepath, violations in report_data.items():
        for violation in violations:
            pattern_id = violation['id']
            if pattern_id not in violation_summary:
                violation_summary[pattern_id] = {
                    'count': 0,
                    'type': violation['type'],
                    'description': violation['description']
                }
            violation_summary[pattern_id]['count'] += 1

    # Print Summary
    print("--- 1. Summary of Violations ---")
    for pattern_id, summary in sorted(violation_summary.items(), key=lambda item: item[1]['count'], reverse=True):
        print(f"[{pattern_id}] ({summary['type'].upper()}): {summary['count']} instances")
        print(f"    -> Description: {summary['description']}")
    print("-" * 35)

    # Print Detailed Report
    print("\n--- 2. Detailed Findings ---")
    for filepath in sorted(report_data.keys()):
        violations = report_data[filepath]
        print(f"\n📁 File: {filepath}")
        print("-" * (len(filepath) + 8))
        
        for violation in violations:
            print(f"  [{violation['id']}] (Line {violation['line']}): {violation['description']}")
            print(f"    Code: '{violation['code_snippet']}'")
            
    print("\n=======================================================")
    print("End of Report.")
    print("=======================================================")


if __name__ == "__main__":
    # Start scanning from the current directory
    repo_root = os.getcwd() 
    
    # You can change repo_root to a specific path if needed, e.g., 
    # repo_root = '/path/to/your/repo'

    all_violations = scan_repository(repo_root)
    generate_report(all_violations)
