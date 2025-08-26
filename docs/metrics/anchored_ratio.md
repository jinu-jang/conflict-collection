# Anchored Ratio

A 3‑way similarity metric `anchored_ratio(O, R, R_hat)` producing a score in [0,1] comparing two edited versions (R, R̂) relative to a base O.

- Denominator normalises over the union of changed base intervals plus insertion slots.
- Numerator rewards aligned equal lines (and optionally per-line Levenshtein similarity) within each union block and insertion slot.

```python
from conflict_collection.metrics.anchored_ratio import anchored_ratio
score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
```

If neither side changes anything (no base changes, no insertions) the score is defined as 1.0.

## When to Use

Useful for measuring convergence of independent resolution attempts, or similarity between automated and manual merges.

## Rationale

Traditional pairwise diffs ignore the role of the base. Anchoring both transformations to O allows fairer comparison of expansion/compression asymmetries and insertion slots.

## API

See [function reference](../api/anchored_ratio_func.md).
