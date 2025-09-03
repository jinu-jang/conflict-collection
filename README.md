# conflict-collection

[![PyPI version](https://badge.fury.io/py/conflict-collection.svg)](https://badge.fury.io/py/conflict-collection)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Versions](https://img.shields.io/pypi/pyversions/conflict-collection.svg)](https://pypi.org/project/conflict-collection/)
[![Downloads](https://pepy.tech/badge/conflict-collection)](https://pepy.tech/project/conflict-collection)

> Data collection toolkit for Git merge conflicts: structural types, social signals, and similarity metrics.

`conflict-collection` builds on [`conflict-parser`](https://github.com/jinu-jang/conflict-parser) to turn raw in-progress merges into rich, typed records suitable for research, analytics, or ML.

---

## ✨ Features

- Classify and enumerate merge conflict cases (modify/modify, add/add, delete/modify, etc.)
- Produce structured frozen dataclasses with per-side contents & resolution metadata
- Build canonical 5‑tuples (A,B,O,M,R) for dataset curation
- Extract social / ownership signals (recency, blame composition, integrator priors)
- Compute a 3‑way anchored similarity ratio between two resolution candidates
- Fully typed (PEP 561) & test‑covered

---

## 📦 Install

```bash
pip install conflict-collection
# or with documentation extras
pip install conflict-collection[docs]
```

---

## 🚀 Quick Start

```python
from conflict_collection.collectors.conflict_type import collect as collect_conflicts
from conflict_collection.collectors.societal import collect as collect_social
from conflict_collection.metrics.anchored_ratio import anchored_ratio

# 1) Enumerate conflict cases after a merge produced conflicts
cases = collect_conflicts(repo_path='.', resolution_sha='<resolved-commit-sha>')
print(len(cases), 'cases')
print(cases[0].conflict_type, cases[0].conflict_path)

# 2) Capture social signals
signals = collect_social(repo_path='.')
for path, rec in signals.items():
	print(path, rec.ours_author, rec.owner_commits_ours)

# 3) Similarity metric example
O = 'line1\nline2\nline3'
R = 'line1\nX\nline3'
R_hat = 'line1\nY\nline3'
print('anchored ratio =', anchored_ratio(O, R, R_hat))
```

---

## 📚 Documentation

Full docs (usage guides + auto-generated API reference) are published with MkDocs & mkdocstrings:

https://jinu-jang.github.io/conflict-collection

Local build:

```bash
pip install -e .[docs]
mkdocs serve
```

---

## 🧩 Data Models

| Model | Purpose |
| ----- | ------- |
| Typed Conflict Cases | Frozen dataclasses per conflict archetype |
| `Conflict5Tuple` | Canonical (A,B,O,M,R) capture |
| Social Signals | Ownership & recency metrics per file |
| Anchored Ratio | Algorithmic similarity between two edits |

---

## 🔬 Testing

```bash
git clone https://github.com/jinu-jang/conflict-collection
cd conflict-collection
pip install -e .[dev]
pytest -q
```

---

## 🤝 Contributing

PRs welcome! Please:

1. Add or update tests
2. Run `black . && isort . && pytest -q`
3. If adding public API, include docstrings & update docs nav (`mkdocs.yml`)

See `docs/contributing.md` for details.

---

## 📄 License

MIT © 2025 Jinu Jang

---

## 🔖 Status

Beta. Interfaces may change before 0.1. Feedback appreciated.