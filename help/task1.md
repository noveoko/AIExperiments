**Here’s a practical, ticket-closing playbook** for this Databricks/Spark source migration. Treat it as a checklist you can walk through (and show your boss) without needing to expose schema or business details.

### 1. Source replacement (table1 + table2 → table3)
- Identify every read of `table1` and `table2` (joins, filters, selects, window functions, UDFs, etc.).
- Map each required column to its equivalent (or derivation) in `table3`. Document the mapping in a short table or comment block.
- Replace the reads with a single source from `table3`. Prefer an explicit column list over `SELECT *`.
- Keep the old tables readable (point 5) but remove them from the live dependency graph.

### 2. Revenue calculation
- Locate the existing revenue logic (wherever it currently lives).
- Move or re-apply that exact logic after the new source is read. Do **not** rewrite the business rules unless the ticket explicitly allows it.
- Confirm the calculation now runs only on `table3` data and no longer touches `table2`.

### 3. Eliminate dependence on table2
- After the rewrite, run a static check (grep / dependency graph / Databricks lineage if available) to prove zero remaining references to `table2` in the production job/notebook/pipeline.
- Remove any temporary staging views or intermediate datasets that still pointed at `table2`.

### 4. Decommission ingestion pipelines
- Disable or delete the scheduled jobs / DLT pipelines / Auto Loader streams that populate `table1` and `table2`.
- Leave the tables themselves in place (point 5). Optionally add a note or table property indicating they are frozen for audit only.
- Confirm the new `table3` ingestion is healthy and the only active upstream.

### 5. Keep table1 / table2 for audit
- Do not drop or rename them.
- Optionally: set them to read-only, add a comment, or move them to an audit schema/database if your org uses one.
- Document retention policy if one exists.

### 6. No functional regressions
- **Data parity checks** (run before/after on the same date range or watermark):
  - Row counts
  - Key aggregates (especially the revenue figure and any downstream metrics that depend on it)
  - Null rates and distinct counts on critical columns
  - Sample row-level comparison on a stratified set of keys
- **Job-level checks**:
  - Same output schema (column names, types, nullability)
  - Same partitioning / clustering if the downstream consumers care
  - Runtime and shuffle metrics stay within acceptable bounds
- Re-run any existing unit / integration tests that cover this pipeline.
- If you have a staging or shadow environment, run the new job side-by-side for a few days and compare outputs.

### Suggested implementation sequence
1. Create a feature branch / new notebook version.
2. Add the column mapping + revenue logic under a clear comment.
3. Write the new read from `table3` and the revenue calculation.
4. Add temporary assertions or data-quality checks that fail the job if parity is broken.
5. Run the full job in a non-prod workspace against recent data.
6. Once green, remove the old reads and the ingestion schedules.
7. Update any job documentation, dashboard links, or runbooks that still mention table1/table2 as live sources.
8. Open the PR / change ticket with the mapping, parity results, and confirmation that table2 is gone from the dependency graph.

### Quick verification script pattern (adapt to your tables)
```python
# After the change, something like this in a validation notebook
old = spark.table("...table1").join(...table2...)  # or the previous final dataset
new = spark.table("...table3")  # + revenue logic

# Basic counts + key metric
assert old.count() == new.count()  # or within tolerance if history is truncated
assert abs(old.agg(sum("revenue")).first()[0] - new.agg(sum("revenue")).first()[0]) < 1e-6

# Column presence
assert set(new.columns) >= set(required_columns)
```

Close the ticket only when:
- All six points above are demonstrably true,
- Parity checks pass,
- Old ingestion is stopped,
- Code and docs no longer reference table2 as a live source.

If you hit a specific sticking point (lineage not updating, schema drift, revenue formula location, etc.) you can describe the symptom without sharing business details and I can help narrow the next step.