"""Anchored 3-way similarity ratio.

The :func:`anchored_ratio` function computes a normalised similarity score in [0,1]
between two edited versions (R and R_hat) with respect to a common base O.
It jointly reasons about:
* Base-anchored change intervals (replacements / expansions / compressions)
* Insertions at base slots
* Optional per-line Levenshtein similarity for partial replacements

Design goals:
1. Reward agreement only inside regions where at least one side changed.
2. Distinguish identical insertions in the same slot from insertions in different slots.
3. Provide a tunable granularity (exact-only vs Levenshtein) without changing semantics.
4. Define the degenerate case (no changes) as 1.0 for stability.
"""

from difflib import SequenceMatcher, unified_diff
from typing import Dict, Literal, Tuple

from Levenshtein import ratio as levenshtein_ratio

Tag = Literal["replace", "delete", "insert", "equal"]


# ----------------------------
# Small utilities
# ----------------------------


def _remove_empty_lines(text: str) -> list[str]:
    """Remove blank/whitespace-only lines to stabilize line accounting."""
    return [line for line in text.splitlines() if line.strip() != ""]


def _opcodes(base_lines: list[str], target_lines: list[str]):
    """Return difflib opcodes between a base and a target (no autojunk)."""
    return SequenceMatcher(a=base_lines, b=target_lines, autojunk=False).get_opcodes()


def _line_similarity(a: str, b: str, use_line_levenshtein: bool) -> float:
    """
    Similarity for two single lines in [0,1]. Exact match = 1.0.
    If Levenshtein is enabled, use python-Levenshtein ratio; else 0.0 for non-equal.
    """
    if a == b:
        return 1.0
    if not use_line_levenshtein:
        return 0.0
    return float(levenshtein_ratio(a, b))


def _aligned_block_score(
    A: list[str], B: list[str], use_line_levenshtein: bool
) -> float:
    """
    Align two line blocks A vs B with SequenceMatcher and score:
      - equal blocks: +exact line count
      - replace blocks: +sum per-line similarity for zipped pairs
      - insert/delete: +0
    Returns a non-negative float (≤ max(len(A), len(B))).
    """
    if not A and not B:
        return 0.0
    sequence_matcher = SequenceMatcher(a=A, b=B, autojunk=False)
    score: float = 0.0
    for tag, a_start, a_end, b_start, b_end in sequence_matcher.get_opcodes():
        if tag == "equal":
            score += a_end - a_start
        elif tag == "replace":
            pair_count = min(a_end - a_start, b_end - b_start)
            for offset in range(pair_count):
                score += _line_similarity(
                    A[a_start + offset],
                    B[b_start + offset],
                    use_line_levenshtein,
                )
        # insert/delete contribute 0
    return score


# ----------------------------
# Base-anchored interval logic
# ----------------------------


def _merged_union_change_intervals(
    O_vs_R: list[Tuple[Tag, int, int, int, int]],
    O_vs_R_hat: list[Tuple[Tag, int, int, int, int]],
) -> list[Tuple[int, int]]:
    """
    Merge base-index intervals [start, end) where either R or R_hat has a change (tag != 'equal').
    """
    change_intervals: list[Tuple[int, int]] = []

    # Scan both to collect change intervals (in base)
    for tag, base_start, base_end, _, _ in O_vs_R:
        if tag != "equal":
            change_intervals.append((base_start, base_end))
    for tag, base_start, base_end, _, _ in O_vs_R_hat:
        if tag != "equal":
            change_intervals.append((base_start, base_end))

    if not change_intervals:
        return []

    change_intervals.sort()
    merged: list[Tuple[int, int]] = [change_intervals[0]]
    for interval_start, interval_end in change_intervals[1:]:
        last_start, last_end = merged[-1]
        if interval_start <= last_end:
            merged[-1] = (last_start, max(last_end, interval_end))
        else:
            merged.append((interval_start, interval_end))
    return merged


def _project_base_subrange_to_target(
    O_vs_target: list[Tuple[Tag, int, int, int, int]],
    target_lines: list[str],
    base_slice_start: int,
    base_slice_end: int,
) -> list[str]:
    """
    Map a base subrange [base_slice_start, base_slice_end) to target lines by
    traversing opcodes that overlap the subrange.

    - equal: copy the 1:1 target slice
    - replace: proportionally map into its [target_start:target_end]
    - delete: no output
    - insert: ignored here (no base span), handled separately per base-slot
    """
    projected_output: list[str] = []
    for tag, base_start, base_end, target_start, target_end in O_vs_target:
        if base_end <= base_slice_start or base_start >= base_slice_end:
            continue
        overlap_start = max(base_slice_start, base_start)
        overlap_end = min(base_slice_end, base_end)
        if overlap_start >= overlap_end:
            continue

        if tag == "delete":
            continue
        if tag == "equal":
            target_from = target_start + (overlap_start - base_start)
            target_to = target_start + (overlap_end - base_start)
            projected_output.extend(target_lines[target_from:target_to])
        elif tag == "replace":
            base_len = base_end - base_start
            target_len = target_end - target_start
            target_from = (
                target_start + ((overlap_start - base_start) * target_len) // base_len
            )
            target_to = (
                target_start + ((overlap_end - base_start) * target_len) // base_len
            )
            projected_output.extend(target_lines[target_from:target_to])
        # 'insert' has no base extent; skip here
    return projected_output


# ----------------------------
# Insertions per base slot
# ----------------------------


def _build_insertions_map(
    O_vs_target: list[Tuple[Tag, int, int, int, int]],
    target_lines: list[str],
) -> Dict[int, list[str]]:
    """
    Build a map of base-slot-index -> list of inserted lines.
    A slot index i means “before base line i” (0..N) where N is len(base).
    """
    insertions_by_slot: Dict[int, list[str]] = {}
    for tag, base_start, _, target_start, target_end in O_vs_target:
        if tag == "insert":
            insertions_by_slot.setdefault(base_start, []).extend(
                target_lines[target_start:target_end]
            )
    return insertions_by_slot


# ----------------------------
# Public API
# ----------------------------


def anchored_ratio(
    O: str, R: str, R_hat: str, *, use_line_levenshtein: bool = True
) -> float:
    """
    3-way anchored line similarity ratio in [0,1] for two edited versions (R, R_hat) against a base O.

    Denominator (base-changes) =
        sum over EACH base line i in each merged union block [union_start, union_end)
            max( 1, len(R_piece_i), len(R_hat_piece_i) )
      where R_piece_i and R_hat_piece_i are projections of [i, i+1) into R and R_hat.

    Numerator (base-changes) =
        (A) sum over base lines i in union blocks:
              +1 if len(R_piece_i)==0 and len(R_hat_piece_i)==0  (mutual delete/compress)
        PLUS
        (B) sum over union blocks:
              aligned score between FULL projected slices of the whole block
              (captures content equality even when it shifts across micro-slices)

    Insertions (per slot):
      - Denominator += max(#ins_R, #ins_Rhat)
      - Numerator   += aligned score between inserted lines

    If total denominator == 0, returns 1.0.
    """
    if R == R_hat:
        return 1.0

    base_lines: list[str] = _remove_empty_lines(O)
    R_lines: list[str] = _remove_empty_lines(R)
    R_hat_lines: list[str] = _remove_empty_lines(R_hat)

    # Opcodes
    O_vs_R = _opcodes(base_lines, R_lines)
    O_vs_R_hat = _opcodes(base_lines, R_hat_lines)

    # Union of changed base intervals
    merged_union_intervals = _merged_union_change_intervals(O_vs_R, O_vs_R_hat)

    denominator_base: int = 0
    numerator_base_mutual_deletes: float = 0.0
    numerator_base_block_align: float = 0.0

    for union_start, union_end in merged_union_intervals:
        # Per-base-line pass (for denom + mutual-deletes credit)
        for i in range(union_start, union_end):  # micro-slices [i, i+1)
            R_piece = _project_base_subrange_to_target(O_vs_R, R_lines, i, i + 1)
            R_hat_piece = _project_base_subrange_to_target(
                O_vs_R_hat, R_hat_lines, i, i + 1
            )

            denominator_base += max(1, len(R_piece), len(R_hat_piece))

            if not R_piece and not R_hat_piece:
                # Both deleted/compressed this base line -> full agreement for this line
                numerator_base_mutual_deletes += 1.0

        # Whole-block content alignment (captures contained equalities like moved lines)
        R_full = _project_base_subrange_to_target(
            O_vs_R, R_lines, union_start, union_end
        )
        R_hat_full = _project_base_subrange_to_target(
            O_vs_R_hat, R_hat_lines, union_start, union_end
        )
        numerator_base_block_align += _aligned_block_score(
            R_full, R_hat_full, use_line_levenshtein
        )

    # Insertions (slot union)
    R_insertions_by_slot = _build_insertions_map(O_vs_R, R_lines)
    R_hat_insertions_by_slot = _build_insertions_map(O_vs_R_hat, R_hat_lines)

    denominator_insertions: int = 0
    numerator_insertions: float = 0.0
    for slot in set(R_insertions_by_slot) | set(R_hat_insertions_by_slot):
        ins_R = R_insertions_by_slot.get(slot, [])
        ins_R_hat = R_hat_insertions_by_slot.get(slot, [])
        denominator_insertions += max(len(ins_R), len(ins_R_hat))
        numerator_insertions += _aligned_block_score(
            ins_R, ins_R_hat, use_line_levenshtein
        )

    total_denominator = denominator_base + denominator_insertions
    if total_denominator == 0:
        return 1.0

    numerator_total = (
        numerator_base_mutual_deletes
        + numerator_base_block_align
        + numerator_insertions
    )
    score = numerator_total / total_denominator
    return max(0.0, min(1.0, score))
