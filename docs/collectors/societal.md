# Societal / Ownership Signals

Captures developer-centric signals for conflicted files to support studies of ownership, expertise, and recency.

## Signals Collected

| Field | Meaning |
| ----- | ------- |
| `ours_author` / `theirs_author` | Last commit authors touching the file on each side |
| `owner_commits_ours` / `_theirs` | Count of commits by the side's latest author since the merge base(s) |
| `age_days_ours` / `_theirs` | Age (days) of last modification relative to merge reference time |
| `integrator_priors.resolver_prev_commits` | Historical commits by the integrator to this file |
| `blame_table` | Aggregated blame at `HEAD` grouped by author |

## Usage

```python
from conflict_collection.collectors.societal import collect

signals = collect(repo_path=".")
for path, rec in signals.items():
    print(path, rec.ours_author, rec.owner_commits_ours, rec.age_days_ours)
```

## Implementation Notes

- Merge bases are computed (could be >1). Ownership counts exclude commits before all bases.
- File list defaults to currently conflicted files; pass an explicit iterable to target arbitrary files.
- Blame aggregation collapses contiguous regions by author and sums line counts.

## API Reference

See [collector function](../api/collect_societal_signals.md).
