#!/usr/bin/env python3
"""
generate_dup_report_with_html.py

Scan a Python repo for repeated/similar functions (text + AST), respect .gitignore,
and write a visual HTML report (single self-contained file).

Usage:
    python generate_dup_report_with_html.py /path/to/repo --output report.html --threshold 0.8

Requirements:
    pip install pathspec

"""
import os
import ast
import difflib
import json
import argparse
from typing import Dict, List, Tuple
import pathspec


# ---- .gitignore loader ----
def load_gitignore_patterns(repo_path: str):
    patterns = []
    for root, _, files in os.walk(repo_path):
        if ".gitignore" in files:
            gitignore_path = os.path.join(root, ".gitignore")
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                lines = [ln.rstrip("\n") for ln in f.readlines()]
                # make patterns relative to repo root
                if lines:
                    # Prepend path to patterns so nested .gitignores work with pathspec
                    rel_root = os.path.relpath(root, repo_path)
                    if rel_root == ".":
                        patterns.extend(lines)
                    else:
                        # For nested .gitignore, prefix patterns with the directory
                        prefixed = [os.path.join(rel_root, p) if p and not p.startswith('/') else p for p in lines]
                        patterns.extend(prefixed)
    if patterns:
        return pathspec.PathSpec.from_lines("gitwildmatch", patterns)
    return None


# ---- AST normalizer ----
class VariableNormalizer(ast.NodeTransformer):
    """Renames variables and argument names to var_1, var_2, ... to reduce noise."""
    def __init__(self):
        super().__init__()
        self.var_map = {}
        self.counter = 0

    def _map(self, name: str) -> str:
        if name not in self.var_map:
            self.counter += 1
            self.var_map[name] = f"var_{self.counter}"
        return self.var_map[name]

    def visit_Name(self, node):
        if isinstance(node.ctx, (ast.Store, ast.Load, ast.Del)):
            node.id = self._map(node.id)
        return node

    def visit_arg(self, node: ast.arg):
        node.arg = self._map(node.arg)
        return node


# ---- code extraction & normalization ----

def extract_functions_from_file(filepath: str) -> Dict[str, Dict[str, str]]:
    """Return mapping of func_unique_id -> {file, name, text, ast}"""
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            code = f.read()
    except Exception:
        return {}

    try:
        tree = ast.parse(code)
    except SyntaxError:
        return {}

    functions = {}
    lines = code.splitlines()

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            start_line = node.lineno - 1
            end_line = getattr(node, "end_lineno", node.lineno)
            func_code = "\n".join(lines[start_line:end_line])

            text_norm = normalize_text(func_code)
            ast_norm = normalize_ast(node)

            unique_id = f"{os.path.abspath(filepath)}::{node.name}::{start_line+1}"  # stable id
            functions[unique_id] = {
                "file": os.path.abspath(filepath),
                "name": node.name,
                "start_line": start_line + 1,
                "text": text_norm,
                "ast": ast_norm,
                "raw": func_code,
            }

    return functions


def normalize_text(code: str) -> str:
    # strip comments and leading/trailing whitespace per line
    code = "\n".join(line.split('#')[0].rstrip() for line in code.splitlines())
    try:
        tree = ast.parse(code)
        tree = VariableNormalizer().visit(tree)
        # ast.unparse -> stable formatting of normalized source (py3.9+)
        normalized = ast.unparse(tree)
        return normalized
    except Exception:
        return code.strip()


def normalize_ast(node: ast.AST) -> str:
    try:
        normalizer = VariableNormalizer()
        normalized_node = normalizer.visit(ast.fix_missing_locations(node))
        # Use ast.dump without attributes to get structural representation
        return ast.dump(normalized_node, annotate_fields=False, include_attributes=False)
    except Exception:
        return ""


# ---- similarity helpers ----

def fuzzy_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def ast_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b).ratio()


def combined_similarity(a: Dict[str, str], b: Dict[str, str], w_text=0.4, w_ast=0.6) -> float:
    t = fuzzy_similarity(a.get("text", ""), b.get("text", ""))
    s = ast_similarity(a.get("ast", ""), b.get("ast", ""))
    return w_text * t + w_ast * s


# ---- main analysis ----

def analyze_repo_code_repetition(repo_path: str, similarity_threshold: float = 0.8) -> Dict:
    spec = load_gitignore_patterns(repo_path)
    all_funcs = []

    for root, _, files in os.walk(repo_path):
        for f in files:
            if not f.endswith('.py'):
                continue
            filepath = os.path.join(root, f)
            relpath = os.path.relpath(filepath, repo_path)
            if spec and spec.match_file(relpath):
                continue

            funcs = extract_functions_from_file(filepath)
            for uid, data in funcs.items():
                all_funcs.append((uid, data))

    total_pairs = 0
    repeated_pairs = []

    for i in range(len(all_funcs)):
        for j in range(i + 1, len(all_funcs)):
            total_pairs += 1
            a = all_funcs[i][1]
            b = all_funcs[j][1]
            sim = combined_similarity(a, b)
            if sim >= similarity_threshold:
                repeated_pairs.append({
                    "a_id": all_funcs[i][0],
                    "b_id": all_funcs[j][0],
                    "file1": a["file"],
                    "func1": a["name"],
                    "start1": a["start_line"],
                    "file2": b["file"],
                    "func2": b["name"],
                    "start2": b["start_line"],
                    "similarity": round(sim, 4),
                    "text1": a.get("text", ""),
                    "text2": b.get("text", ""),
                    "ast1": a.get("ast", ""),
                    "ast2": b.get("ast", ""),
                    "raw1": a.get("raw", ""),
                    "raw2": b.get("raw", ""),
                })

    repetition_ratio = len(repeated_pairs) / max(total_pairs, 1)
    report = {
        "total_functions": len(all_funcs),
        "total_pairs_compared": total_pairs,
        "similar_function_pairs": repeated_pairs,
        "repetition_ratio": round(repetition_ratio * 100, 2),
    }
    return report


# ---- HTML emitter ----
HTML_TEMPLATE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Code Duplication Report</title>
<style>
  body{font-family:Inter, ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial; margin:20px}
  h1{font-size:1.4rem}
  .summary{margin-bottom:12px}
  table{width:100%; border-collapse:collapse; margin-top:12px}
  th,td{padding:8px; border:1px solid #ddd; text-align:left}
  th{cursor:pointer; background:#f7f7f7}
  tr:hover{background:#f1f7ff}
  .badge{display:inline-block;padding:4px 8px;border-radius:6px;background:#eef}
  .controls{margin-bottom:12px}
  .code{white-space:pre;background:#111;color:#efe;padding:8px;border-radius:6px;overflow:auto;max-height:300px}
  .modal{position:fixed;left:0;top:0;width:100%;height:100%;background:rgba(0,0,0,0.5);display:none;align-items:center;justify-content:center}
  .modal .sheet{background:#fff;padding:16px;border-radius:8px;max-width:1000px;max-height:90%;overflow:auto}
  .close{float:right;cursor:pointer}
  input[type=search]{padding:6px;margin-right:8px}
  .small{font-size:0.9rem;color:#555}
</style>
</head>
<body>
<h1>Code Duplication Report</h1>
<div class="summary">
  <div>Total functions analyzed: <strong id="total-funcs"></strong></div>
  <div>Total pairs compared: <strong id="total-pairs"></strong></div>
  <div>Repetition ratio: <span class="badge" id="repetition-ratio"></span></div>
</div>
<div class="controls">
  <label>Filter similarity ≥ <input id="sim-threshold" type="number" value="0.8" min="0" max="1" step="0.01"></label>
  <label>Search: <input id="search" type="search" placeholder="file or function name"></label>
  <button id="apply">Apply</button>
</div>
<table id="pairs-table">
  <thead>
    <tr>
      <th data-col="similarity">Similarity</th>
      <th data-col="file1">File 1</th>
      <th data-col="func1">Function 1</th>
      <th data-col="file2">File 2</th>
      <th data-col="func2">Function 2</th>
      <th data-col="actions">Actions</th>
    </tr>
  </thead>
  <tbody></tbody>
</table>

<div id="modal" class="modal" onclick="hideModal(event)">
  <div class="sheet" onclick="event.stopPropagation()">
    <div class="close" onclick="document.getElementById('modal').style.display='none'">✖</div>
    <div id="modal-body"></div>
  </div>
</div>

<script>
// Embedded report data
const REPORT = __REPORT_JSON__;

function human(n){ return (n*100).toFixed(2) + '%'; }

function populateSummary(){
  document.getElementById('total-funcs').innerText = REPORT.total_functions;
  document.getElementById('total-pairs').innerText = REPORT.total_pairs_compared;
  document.getElementById('repetition-ratio').innerText = REPORT.repetition_ratio + '%';
}

function renderTable(minSim=0.8, q=''){
  const tbody = document.querySelector('#pairs-table tbody');
  tbody.innerHTML = '';
  const rows = REPORT.similar_function_pairs
    .filter(r => r.similarity >= minSim && (
      r.file1.includes(q) || r.file2.includes(q) || r.func1.includes(q) || r.func2.includes(q)
    ));

  rows.sort((a,b)=>b.similarity - a.similarity);

  for(const r of rows){
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${r.similarity.toFixed(3)}</td>
      <td title="${r.file1}">${shorten(r.file1)}</td>
      <td>${escapeHtml(r.func1)} <div class="small">line ${r.start1}</div></td>
      <td title="${r.file2}">${shorten(r.file2)}</td>
      <td>${escapeHtml(r.func2)} <div class="small">line ${r.start2}</div></td>
      <td><button onclick='showPair("${r.a_id}", "${r.b_id}")'>View</button></td>
    `;
    tbody.appendChild(tr);
  }
}

function shorten(path){
  if(path.length>60) return '...'+path.slice(-60);
  return path;
}

function escapeHtml(s){ return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

function applyFilters(){
  const sim = parseFloat(document.getElementById('sim-threshold').value) || 0;
  const q = document.getElementById('search').value.trim();
  renderTable(sim, q);
}

function showPair(a_id, b_id){
  const pair = REPORT.similar_function_pairs.find(r=>r.a_id===a_id && r.b_id===b_id);
  if(!pair) return;
  const body = document.getElementById('modal-body');
  body.innerHTML = `
    <h3>Similarity: ${pair.similarity.toFixed(3)}</h3>
    <h4>${pair.file1} :: ${pair.func1} (line ${pair.start1})</h4>
    <div class="code">${escapeHtml(pair.raw1)}</div>
    <h4>${pair.file2} :: ${pair.func2} (line ${pair.start2})</h4>
    <div class="code">${escapeHtml(pair.raw2)}</div>
    <h4>Normalized Text Form (for comparison)</h4>
    <div class="code">${escapeHtml(pair.text1)}</div>
    <div class="code">${escapeHtml(pair.text2)}</div>
    <h4>AST Dumps</h4>
    <div class="code">${escapeHtml(pair.ast1)}</div>
    <div class="code">${escapeHtml(pair.ast2)}</div>
  `;
  document.getElementById('modal').style.display = 'flex';
}

function hideModal(e){
  if(e.target.id==='modal') document.getElementById('modal').style.display='none';
}

// sorting support
const headers = document.querySelectorAll('th[data-col]');
headers.forEach(h=>{
  h.addEventListener('click', ()=>{
    const col = h.getAttribute('data-col');
    sortBy(col);
  });
});

function sortBy(col){
  REPORT.similar_function_pairs.sort((a,b)=>{
    if(col==='similarity') return b.similarity - a.similarity;
    return (''+a[col]).localeCompare(''+b[col]);
  });
  applyFilters();
}

// init
populateSummary();
renderTable(parseFloat(document.getElementById('sim-threshold').value), '');
document.getElementById('apply').addEventListener('click', applyFilters);

</script>
</body>
</html>
"""


def write_html_report(report: Dict, out_path: str):
    # Embed JSON into HTML (minimize size)
    json_blob = json.dumps(report)
    html = HTML_TEMPLATE.replace('__REPORT_JSON__', json_blob)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"Wrote HTML report to: {out_path}")


# ---- CLI ----

def main():
    p = argparse.ArgumentParser(description='Generate duplication report with HTML output')
    p.add_argument('repo', help='path to repository')
    p.add_argument('--output', '-o', default='duplication_report.html', help='output HTML file')
    p.add_argument('--threshold', '-t', type=float, default=0.8, help='similarity threshold (0..1)')
    args = p.parse_args()

    repo = os.path.abspath(args.repo)
    if not os.path.isdir(repo):
        print('Repo path is not a directory')
        return

    print('Scanning repo (this may take a while)...')
    report = analyze_repo_code_repetition(repo, similarity_threshold=args.threshold)
    write_html_report(report, args.output)
    print('Done.')


if __name__ == '__main__':
    main()
