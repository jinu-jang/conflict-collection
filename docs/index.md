# Conflict Collection

> Data collection toolkit for Git merge conflicts: structural types, social signals, and similarity metrics.

`conflict-collection` builds on [`conflict-parser`](https://github.com/jinu-jang/conflict-parser) to let you:

- Enumerate and classify raw merge conflict cases (modify-modify, delete-modify, add-add, etc.)
- Capture rich 5‑tuple representations (A / B / O / M / R) suitable for ML datasets
- Extract social / ownership signals (recency, blame composition, prior integrator behaviour)
- Compute research-oriented metrics like the 3‑way anchored similarity ratio

## Why this exists

Academic & engineering studies of merge conflicts often re‑implement similar collection logic scattered across scripts. This project offers a typed, test‑covered, reusable core to standardise merge conflict data pipelines.

## Core Concepts

| Concept | Description |
| ------- | ----------- |
| Conflict Case | A single logical conflict instance (may aggregate multiple Git index stages) |
| 5‑Tuple | Ordered versions: ours (A), theirs (B), base/virtual base (O), conflicted (M), resolved (R) |
| Social Signals | Ownership & recency meta-data helpful for predicting / understanding resolution difficulty |
| Anchored Ratio | A 3‑way normalised similarity score R vs R̂ relative to base O |

## Install

```bash
pip install conflict-collection
# or with docs extras
pip install conflict-collection[docs]
```

## Quick Links

- [Quick Start](quickstart.md)
- [Conflict Type Collector](collectors/conflict_types.md)
- [Societal Signals Collector](collectors/societal.md)
- [Anchored Ratio Metric](metrics/anchored_ratio.md)
- [Data Models](models/typed_conflict_cases.md)
- [API Reference](api/collect_conflict_types.md)

## Status

Beta. Interfaces may refine prior to 0.1. Feedback & PRs welcome.
