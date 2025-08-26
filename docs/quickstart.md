# Quick Start

This walks you through collecting conflict cases, social signals, and computing the anchored ratio.

## 1. Prepare a repo in a conflicted merge state

You need a repository where `git merge <branch>` produced conflicts and stopped.

```bash
# Example skeleton (simplified)
git clone <your-repo>
cd <your-repo>
git checkout feature-A
git merge feature-B  # leaves conflicts
```

## 2. Collect typed conflict cases

```python
from conflict_collection.collectors.conflict_type import collect as collect_conflicts

cases = collect_conflicts(repo_path=".", resolution_sha="<post-resolution-commit-sha>")
print(len(cases), "cases")
first = cases[0]
print(first.conflict_type, first.conflict_path)
```

Each element is a frozen dataclass such as `ModifyModifyConflictCase` with fields:
`base_content`, `ours_content`, `theirs_content`, `conflict_body`, `resolved_body`, etc.

## 3. Social / ownership signals

```python
from conflict_collection.collectors.societal import collect as collect_social

signals = collect_social(repo_path=".")  # dict[path -> SocialSignalsRecord]
for path, record in signals.items():
    print(path, record.ours_author, record.owner_commits_ours)
```

## 4. Anchored similarity metric

```python
from conflict_collection.metrics.anchored_ratio import anchored_ratio

O = """line1\nline2\nline3"""
R = """line1\nX\nline3"""
R_hat = """line1\nY\nline3"""
score = anchored_ratio(O, R, R_hat)
print(score)  # float in [0,1]
```

## 5. Building 5‑tuples

If you need the (A,B,O,M,R) representation for ML pipelines, convert a conflict case + raw merge config into a `Conflict5Tuple` (see [model docs](models/five_tuple.md)).

## 6. Reproducible tests

Clone this repo and run:

```bash
pip install -e .[dev]
pytest -q
```

## 7. Next steps

- Explore the [metrics](metrics/anchored_ratio.md)
- Inspect auto-generated [API Reference](api/collect_conflict_types.md)
- Contribute improvements (see [Contributing](contributing.md))
