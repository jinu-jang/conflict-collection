# Diff Similarity (Text IoU)

## What this metric measures (high-level)

Diff Similarity (Text IoU) quantifies how similar two *diffs* are when both are derived from the same base text. Given a base version `O` and two edited versions `R` and `R̂` (R-hat), the metric scores how much the changes in `R` agree with the changes in `R̂`, ignoring parts that neither side touched. In practice, this acts as a faithful 3-way text similarity: it only rewards agreement inside regions where at least one side changed.

The idea mirrors Intersection over Union (IoU) in computer vision: treat "changed text" as the set to compare. The intersection is the overlap of edited content and inserted lines between `R` and `R̂`; the union is the total edited/inserted content from either side. The score is in `[0, 1]`.

This generalizes to any text triplet *(base, version A, version B)*—you choose which version is the common base.

## Why this matters

Traditional pairwise similarity breaks down:

| Situation | Problem |
| - | - |
| Only comparing `R` vs `R̂` | No normalization; “700-character diff” alone says nothing about agreement. |
| Normalizing by full file size | Over-normalization: `700 chars / 12k lines ≈ ~95% similar`|
| Token-level Jaccard | 2-way diff that ignores position and repeated tokens; can reward spurious overlap. |

By comparing only the diffs relative to `O`, Diff Similarity (Text IoU):

* Ignores unchanged context (no accidental inflation from large files).
* Penalizes too many edits (big union with little overlap).
* Penalizes too few shared edits (disjoint or mismatched changes).
* Rewards aligned changes (same replacements/insertions, optionally tolerant of small textual drift).

## Simple examples

1. Disjoint edits\
   You change 5 lines; I change a *different* 5 lines.\
   **Intersection = 0**,\
   **Union = 10 ⇒ Score = 0.0 (0 / 10)**

2. Partial overlap\
   You change 5 lines; I change 5 lines; 2 lines are identical.\
   **Union = 3 (yours-only) + 2 (shared) + 3 (mine-only) = 8**,\
   **Intersection = 2 ⇒ Score = 2/8 = 0.25**

## Formal definition (what’s counted)

Let O be the base (line-tokenized with blank/whitespace-only lines removed), and `R`, `R̂` be two edited versions. We compute diffs `O→R` and `O→R̂` using `difflib.SequenceMatcher` with `autojunk=False`. The metric has two families of components:
- Base-anchored changes (what each base line turned into across both versions)
- Insertions between base lines ("slots")

### Score

Let

- `U_base`: union mass from base-anchored changes
- `U_inserts`: union mass from per-slot insertions
- `I_base_delete`: mutual delete/compress credit
- `A_blocks`: alignment credit within base-anchored union blocks
- `A_inserts`: alignment credit for per-slot insertions

Then

$$
\mathrm{DiffSimilarity}(O,R,\hat{R}) =
\begin{cases}
1.0, & \text{if } R=\hat{R} \\[6pt]
\dfrac{I_{\text{base\_delete}} + A_{\text{blocks}} + A_{\text{inserts}}}
      {U_{\text{base}} + U_{\text{inserts}}}, & \text{otherwise.}
\end{cases}
$$

If the denominator is 0 (no changes anywhere), return 1.0.

## Counting the Union (denominator)

We first find where to look:

1. Compute opcodes for `O→R` and `O→R̂` with `autojunk=False`.
2. Collect all base spans from both diffs whose tag ≠ `equal` (i.e., `replace` or `delete`).
3. Sort and merge overlaps to get merged union blocks `U = {[u_start, u_end)}`.
   Everything outside `U` is ignored.

Inside each union block, we evaluate per-base-line "micro-slices" `[i, i+1)` by projecting them into each target:

* `equal`: 1:1 mapping → one target line
* `replace`: proportionally map into the target block (handles expansion/compression)
* `delete`: maps to nothing (empty list)
* `insert`: has no base span; handled separately in *Insertions by slot*

Denote the projected pieces as `R_i` and `R̂_i` (each a list of 0..k lines).

### Base-anchored union $U_{base}$

For every micro-slice `i` in every union block:

```
U_base += max(1, |R_i|, |R̂_i|)
```

*The floor of 1 ensures that a mutual delete/compress still contributes one unit of *changed capacity*.

### Insertions union $U_{inserts}$

Insertions are grouped by slot index `s ∈ {0..N}`, meaning before base line `s`. Build:

* `Ins_R[s]`: list of lines inserted by R at slot `s`
* `Ins_R̂[s]`: list of lines inserted by R̂ at slot `s`

For every slot `s`:

```
U_inserts += max(|Ins_R[s]|, |Ins_R̂[s]|)
```

> Position matters. Identical text inserted at different slots does not count as overlapping union or intersection.


## Counting the Intersection (numerator)

The numerator is the overlap achieved in three ways:

### Mutual delete/compress $I_{base\_delete}$

For each micro-slice `i` in the base-anchored union:

```
if |R_i| == 0 and |R̂_i| == 0:
    I_base_delete += 1
```

Both sides removed/compressed the same base line ⇒ perfect agreement for that line.

### Alignment within base-anchored blocks $A_{blocks}$

For each union block `[u_start, u_end)`:

1. Project the entire block to each target to get `R_full` and `R̂_full`.
2. Align these sequences of lines with `Align(·,·)` (defined below) to obtain a non-negative score:

```
A_blocks += Align(R_full, R̂_full)
```

This captures matches that move within the block (e.g., a line reorders inside the changed region).

### Alignment of per-slot insertions $A_{inserts}$

For every slot `s`:

```
A_inserts += Align(Ins_R[s], Ins_R̂[s])
```

Alignment is per slot, preserving the “same place, same content” principle.


## How `Align(A, B)` scores text

`Align(A, B)` aligns two line sequences with `SequenceMatcher(autojunk=False)`:

* `equal` blocks: add the exact matching line count.
* `replace` blocks: zip the two sides and, for each paired line, add

  * 1.0 if the lines are exactly equal, or
  * Levenshtein ratio ∈ \[0,1] if `use_line_levenshtein=True`; 0.0 otherwise.
* `insert`/`delete` during alignment: contribute 0.

This yields a granular intersection: exact when desired, tolerant of small textual drift when enabled.


## Change-type “counting rules” at a glance

| Change type (vs base) | Union contribution | Intersection contribution |
| - | - | - |
| Replace / Edit | `max(1, #R_i, #R̂_i)` per micro-slice | From `Align(R_full, R̂_full)`; partial per-line credit if Levenshtein is enabled. |
| Delete (one side) | Same `max(...)` ensures ≥1 | Only if the *other* side also removes/compresses (via I\_base\_delete). |
| Mutual Delete / Compress   | Adds 1 per base line | Adds 1 per base line (I\_base\_delete) ⇒ perfect agreement on deletion. |
| Expansion (1→k lines) | Up to `k` if the other side expands less | Overlap via `Align(·)` if expanded content matches. |
| Compression (k→1 or k→0) | Longer projection wins in `max(...)` | Overlap via mutual delete or alignment of surviving lines. |
| Pure Insert (no base span) | Per slot: `max(#ins_R, #ins_R̂)` | Per slot: `Align(Ins_R, Ins_R̂)`; different slots get 0. |
