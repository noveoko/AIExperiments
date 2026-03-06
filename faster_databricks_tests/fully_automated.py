import os
import re
import json
import time
from collections import defaultdict
from pyspark.sql import SparkSession

# --- CONFIG ---
TEST_DIR = "tests"               # folder with your tests
SNAPSHOT_DIR = "tests/data_snapshots"
TIME_THRESHOLD = 5               # seconds; tables slower than this will be snapshotted
TABLE_ACCESS_PATTERN = re.compile(r"spark\.table\(['\"]([\w\.]+)['\"]\)")

# --- UTILS ---
def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path)

def extract_code_from_notebook(nb_path):
    """Extract code cells from .ipynb"""
    with open(nb_path, "r", encoding="utf-8") as f:
        nb = json.load(f)
    code_cells = []
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            code_cells.append("".join(cell.get("source", [])))
    return "\n".join(code_cells)

def time_table_access(spark, table_name):
    """Access table and measure time"""
    start = time.time()
    try:
        df = spark.table(table_name)
        df.count()  # force evaluation
    except Exception as e:
        return None, str(e)
    elapsed = time.time() - start
    return df, elapsed

def generate_snapshot(df, table_name, snapshot_dir):
    """Save DataFrame as Parquet snapshot"""
    snapshot_path = os.path.join(snapshot_dir, table_name.replace(".", "_"))
    df.write.mode("overwrite").parquet(snapshot_path)
    return snapshot_path

def find_test_files(directory):
    """Recursively find all test files"""
    for root, _, files in os.walk(directory):
        for f in files:
            if f.endswith(".py") or f.endswith(".ipynb"):
                yield os.path.join(root, f)

def rewrite_test_file(file_path, table_snapshots):
    """Rewrite table accesses in test file to use snapshots"""
    if file_path.endswith(".ipynb"):
        with open(file_path, "r", encoding="utf-8") as f:
            nb = json.load(f)
        changed = False
        for cell in nb.get("cells", []):
            if cell.get("cell_type") == "code":
                source_lines = cell.get("source", [])
                new_lines = []
                for line in source_lines:
                    match = TABLE_ACCESS_PATTERN.search(line)
                    if match and match.group(1) in table_snapshots:
                        snapshot_path = table_snapshots[match.group(1)]
                        line = f'spark.read.parquet("{snapshot_path}")\n'
                        changed = True
                    new_lines.append(line)
                cell["source"] = new_lines
        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(nb, f, indent=1)
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        new_lines = []
        changed = False
        for line in lines:
            match = TABLE_ACCESS_PATTERN.search(line)
            if match and match.group(1) in table_snapshots:
                snapshot_path = table_snapshots[match.group(1)]
                line = f'spark.read.parquet("{snapshot_path}")\n'
                changed = True
            new_lines.append(line)
        if changed:
            with open(file_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

# --- MAIN ---
if __name__ == "__main__":
    spark = SparkSession.builder \
        .appName("AutoSnapshotTests") \
        .master("local[*]") \
        .getOrCreate()

    ensure_dir(SNAPSHOT_DIR)

    # Step 1: Scan tests for table accesses
    table_counts = defaultdict(int)
    test_files = list(find_test_files(TEST_DIR))
    for path in test_files:
        if path.endswith(".ipynb"):
            content = extract_code_from_notebook(path)
        else:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        for match in TABLE_ACCESS_PATTERN.findall(content):
            table_counts[match] += 1

    # Step 2: Measure table access times and generate snapshots
    table_snapshots = {}
    for table in table_counts:
        df, elapsed = time_table_access(spark, table)
        if df is None:
            print(f"⚠️ Could not read table '{table}': {elapsed}")
            continue
        if elapsed > TIME_THRESHOLD or table_counts[table] > 1:
            snapshot_path = generate_snapshot(df, table, SNAPSHOT_DIR)
            table_snapshots[table] = snapshot_path
            print(f"💾 Snapshot created for '{table}' ({elapsed:.2f}s) -> {snapshot_path}")
        else:
            print(f"✅ Table '{table}' fast enough ({elapsed:.2f}s), skipping snapshot")

    # Step 3: Rewrite tests to use snapshots
    for path in test_files:
        rewrite_test_file(path, table_snapshots)

    spark.stop()
    print("\nAll snapshots saved and tests rewritten for snapshot usage.")
    print("Snapshot paths:")
    for t, p in table_snapshots.items():
        print(f"  {t} -> {p}")