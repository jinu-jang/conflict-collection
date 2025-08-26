"""
Implements a 3-way similarity ratio.
Checks similarity of the edits from two edited versions (R, R_hat) against a base (O).
"""

from difflib import SequenceMatcher
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
        if tag != "equal" and base_start < base_end:
            change_intervals.append((base_start, base_end))
    for tag, base_start, base_end, _, _ in O_vs_R_hat:
        if tag != "equal" and base_start < base_end:
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


def _micro_boundaries_for_union(
    merged_union_intervals: list[Tuple[int, int]],
    O_vs_R: list[Tuple[Tag, int, int, int, int]],
    O_vs_R_hat: list[Tuple[Tag, int, int, int, int]],
) -> list[Tuple[int, int, list[int]]]:
    """
    For each merged union interval [union_start, union_end), collect micro-boundaries:
      {union_start, opcode boundaries strictly inside, union_end}.
    These micro-intervals are used only for denominator accounting.
    """
    results: list[Tuple[int, int, list[int]]] = []
    for union_start, union_end in merged_union_intervals:
        boundary_points = {union_start, union_end}
        for tag, base_start, base_end, _, _ in O_vs_R:
            if union_start < base_start < union_end:
                boundary_points.add(base_start)
            if union_start < base_end < union_end:
                boundary_points.add(base_end)
        for tag, base_start, base_end, _, _ in O_vs_R_hat:
            if union_start < base_start < union_end:
                boundary_points.add(base_start)
            if union_start < base_end < union_end:
                boundary_points.add(base_end)
        results.append((union_start, union_end, sorted(boundary_points)))
    return results


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


def _expanded_projections_for_union(
    O_vs_target: list[Tuple[Tag, int, int, int, int]],
    target_lines: list[str],
    merged_union_intervals: list[Tuple[int, int]],
) -> list[Tuple[int, int, list[str]]]:
    """
    For each merged union block [union_start, union_end), precompute the FULL projected slice
    (concatenating across opcodes). These are used:
      (a) as whole-block inputs to the numerator alignment,
      (b) for proportional cutting into micro-slices if needed.
    """
    expanded_projections: list[Tuple[int, int, list[str]]] = []
    for union_start, union_end in merged_union_intervals:
        full_projection = _project_base_subrange_to_target(
            O_vs_target, target_lines, union_start, union_end
        )
        expanded_projections.append((union_start, union_end, full_projection))
    return expanded_projections


def _slice_from_expanded_projection(
    expanded_projection: Tuple[int, int, list[str]],
    base_slice_start: int,
    base_slice_end: int,
) -> list[str]:
    """
    Cut [base_slice_start, base_slice_end) out of a pre-expanded union block proportionally.
    """
    union_start, union_end, full_projected_lines = expanded_projection
    projected_length = len(full_projected_lines)
    union_span = union_end - union_start
    if union_span <= 0:
        return []
    projected_from = ((base_slice_start - union_start) * projected_length) // union_span
    projected_to = ((base_slice_end - union_start) * projected_length) // union_span
    return full_projected_lines[projected_from:projected_to]


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
    for tag, base_start, base_end, target_start, target_end in O_vs_target:
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

    Denominator =
        sum over micro-boundaries (inside each merged union block [union_start, union_end)) of
            max( base_span_len, len(R_piece), len(R_hat_piece) )
      + sum over insertion slots of max( #insertions_R, #insertions_R_hat )

    Numerator =
        sum over merged union blocks [union_start, union_end) of aligned score between the FULL projected slices
        (re-align R[union_block] vs R_hat[union_block] with SequenceMatcher; equal lines = 1, replace = per-line sim)
      + sum over insertion slots of aligned score between inserted lines

    If denom == 0, returns 1.0 (no changes by either side).
    """
    if R == R_hat:
        return 1.0

    base_lines: list[str] = _remove_empty_lines(O)
    R_lines: list[str] = _remove_empty_lines(R)
    R_hat_lines: list[str] = _remove_empty_lines(R_hat)

    # Opcodes O vs R and O vs R_hat
    O_vs_R = _opcodes(base_lines, R_lines)
    O_vs_R_hat = _opcodes(base_lines, R_hat_lines)

    # Merged union blocks where at least one side changed
    merged_union_intervals = _merged_union_change_intervals(O_vs_R, O_vs_R_hat)

    # ---- Denominator (base-changes) via micro-boundaries on ORIGINAL projections
    denominator_base: int = 0
    for union_start, union_end, boundary_points in _micro_boundaries_for_union(
        merged_union_intervals, O_vs_R, O_vs_R_hat
    ):
        for micro_start, micro_end in zip(boundary_points[:-1], boundary_points[1:]):
            if micro_start >= micro_end:
                continue
            R_piece = _project_base_subrange_to_target(
                O_vs_R, R_lines, micro_start, micro_end
            )
            R_hat_piece = _project_base_subrange_to_target(
                O_vs_R_hat, R_hat_lines, micro_start, micro_end
            )
            denominator_base += max(
                micro_end - micro_start, len(R_piece), len(R_hat_piece)
            )

    # ---- Numerator (base-changes) via WHOLE-block alignment on EXPANDED projections
    numerator_base: float = 0.0
    expanded_R_projections = _expanded_projections_for_union(
        O_vs_R, R_lines, merged_union_intervals
    )
    expanded_R_hat_projections = _expanded_projections_for_union(
        O_vs_R_hat, R_hat_lines, merged_union_intervals
    )
    for index, (union_start, union_end) in enumerate(merged_union_intervals):
        R_full_slice = _slice_from_expanded_projection(
            expanded_R_projections[index], union_start, union_end
        )
        R_hat_full_slice = _slice_from_expanded_projection(
            expanded_R_hat_projections[index], union_start, union_end
        )
        numerator_base += _aligned_block_score(
            R_full_slice, R_hat_full_slice, use_line_levenshtein
        )

    # ---- Insertions (slot union)
    R_insertions_by_slot = _build_insertions_map(O_vs_R, R_lines)
    R_hat_insertions_by_slot = _build_insertions_map(O_vs_R_hat, R_hat_lines)

    denominator_insertions: int = 0
    numerator_insertions: float = 0.0
    for slot_index in set(R_insertions_by_slot.keys()) | set(
        R_hat_insertions_by_slot.keys()
    ):
        inserted_R_lines = R_insertions_by_slot.get(slot_index, [])
        inserted_R_hat_lines = R_hat_insertions_by_slot.get(slot_index, [])
        denominator_insertions += max(len(inserted_R_lines), len(inserted_R_hat_lines))
        numerator_insertions += _aligned_block_score(
            inserted_R_lines, inserted_R_hat_lines, use_line_levenshtein
        )

    total_denominator = denominator_base + denominator_insertions
    if total_denominator == 0:
        return 1.0

    score = (numerator_base + numerator_insertions) / total_denominator
    return max(0.0, min(1.0, score))
