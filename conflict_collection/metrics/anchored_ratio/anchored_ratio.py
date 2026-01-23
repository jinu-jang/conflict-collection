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

Verbose debugging:
- When verbose=True, this module emits detailed debug logs showing *exactly* what
  contributed to each of the five components in the IoU-like ratio.
- NOTE: line indices reported are based on the filtered line lists produced by
  _remove_empty_lines() (blank/whitespace-only lines removed).
"""

import logging
from dataclasses import dataclass
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


def _project_base_subrange_to_target_with_indices(
    O_vs_target: list[Tuple[Tag, int, int, int, int]],
    target_lines: list[str],
    base_slice_start: int,
    base_slice_end: int,
) -> list[tuple[int, str]]:
    """
    Like _project_base_subrange_to_target, but returns (target_line_index, line_text).
    Indices refer to the filtered target_lines list (_remove_empty_lines output).
    """
    out: list[tuple[int, str]] = []
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
            for j in range(target_from, target_to):
                out.append((j, target_lines[j]))
        elif tag == "replace":
            base_len = base_end - base_start
            target_len = target_end - target_start
            target_from = (
                target_start + ((overlap_start - base_start) * target_len) // base_len
            )
            target_to = (
                target_start + ((overlap_end - base_start) * target_len) // base_len
            )
            for j in range(target_from, target_to):
                out.append((j, target_lines[j]))
        # 'insert' has no base extent; skip here
    return out


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


def _build_insertions_map_with_indices(
    O_vs_target: list[Tuple[Tag, int, int, int, int]],
    target_lines: list[str],
) -> Dict[int, list[tuple[int, str]]]:
    """
    Like _build_insertions_map, but values are (target_line_index, line_text) tuples.
    Indices refer to filtered target_lines list.
    """
    insertions_by_slot: Dict[int, list[tuple[int, str]]] = {}
    for tag, base_start, _, target_start, target_end in O_vs_target:
        if tag == "insert":
            slot_list = insertions_by_slot.setdefault(base_start, [])
            for j in range(target_start, target_end):
                slot_list.append((j, target_lines[j]))
    return insertions_by_slot


# ----------------------------
# Public API
# ----------------------------


def anchored_ratio(
    O: str,
    R: str,
    R_hat: str,
    *,
    use_line_levenshtein: bool = True,
    verbose: bool = False,
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

    Verbose logging (verbose=True):
      Emits debug statements showing:
        - which base lines contributed to denominator_base
        - which base lines earned mutual delete/compress credit
        - which lines aligned (equal/replace pairs) inside each union block alignment
        - which inserted lines aligned per slot
      Indices are based on filtered line arrays (blank lines removed).
    """

    @dataclass
    class Components:
        """Decomposition of the Diff Similarity (Text IoU) score."""

        denominator_base: int = 0
        """Union mass from base-anchored change regions (micro-slices of base lines within merged union blocks).
        For each base micro-slice [i,i+1) inside a union block, we add:
            max(1, len(R_piece_i), len(R_hat_piece_i))
        The floor of 1 means mutual delete/compress still consumes 1 unit of union capacity.
        """

        denominator_insertions: int = 0
        """Union mass from insertions grouped by base slot.
        For each slot s, we add:
            max(len(Ins_R[s]), len(Ins_R_hat[s]))
        """

        numerator_base_mutual_deletes: float = 0.0
        """Intersection credit for mutual delete/compress of the same base line.
        For each base micro-slice [i,i+1) inside a union block:
            if len(R_piece_i)==0 and len(R_hat_piece_i)==0: +1.0
        """

        numerator_base_block_align: float = 0.0
        """Intersection credit from aligning the *full projected content* of each merged union block.
        For each union block [u_start,u_end):
            + Align(R_full_block, R_hat_full_block)
        where Align counts exact equals and (optionally) Levenshtein similarity in replace pairs.
        """

        numerator_insertions: float = 0.0
        """Intersection credit from aligning insertions per base slot.
        For each slot s:
            + Align(Ins_R[s], Ins_R_hat[s])
        """

    comps = Components()

    logger = logging.getLogger(__name__)
    if verbose:
        # "Activate debug logging" without permanently mutating global logging config.
        logger.setLevel(logging.DEBUG)
        if not logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(logging.DEBUG)
            formatter = logging.Formatter("%(levelname)s:%(name)s:%(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        logger.propagate = False  # avoid double-print if root logger also configured

    def _short(s: str, limit: int = 160) -> str:
        s = s.replace("\t", "    ")
        return s if len(s) <= limit else (s[: limit - 1] + "…")

    def _fmt_indexed(lines: list[tuple[int, str]], max_items: int = 8) -> str:
        if not lines:
            return "[]"
        shown = lines[:max_items]
        inner = ", ".join([f"{i}:{_short(t)!r}" for i, t in shown])
        if len(lines) > max_items:
            inner += f", …(+{len(lines)-max_items})"
        return "[" + inner + "]"

    def _aligned_block_score_verbose(
        A: list[str],
        B: list[str],
        *,
        label: str,
        A_origin: str,
        B_origin: str,
        use_line_levenshtein_: bool,
    ) -> float:
        """
        Same semantics as _aligned_block_score, but logs each contributing decision.
        A_origin/B_origin are strings like "R" / "R_hat" for readability.
        """
        if not A and not B:
            if verbose:
                logger.debug("%s: Align(%s,%s): both empty -> +0.0", label, A_origin, B_origin)
            return 0.0

        sm = SequenceMatcher(a=A, b=B, autojunk=False)
        score = 0.0
        if verbose:
            logger.debug(
                "%s: Align(%s,%s): len(A)=%d len(B)=%d", label, A_origin, B_origin, len(A), len(B)
            )

        for tag, a0, a1, b0, b1 in sm.get_opcodes():
            if tag == "equal":
                delta = float(a1 - a0)
                score += delta
                if verbose:
                    for k in range(a0, a1):
                        logger.debug(
                            "%s:   equal  %s[%d] == %s[%d]  -> +1.0  (%r)",
                            label,
                            A_origin,
                            k,
                            B_origin,
                            b0 + (k - a0),
                            _short(A[k]),
                        )
            elif tag == "replace":
                pair_count = min(a1 - a0, b1 - b0)
                if verbose:
                    logger.debug(
                        "%s:   replace %s[%d:%d] vs %s[%d:%d] (pair_count=%d)",
                        label,
                        A_origin,
                        a0,
                        a1,
                        B_origin,
                        b0,
                        b1,
                        pair_count,
                    )
                for off in range(pair_count):
                    a_line = A[a0 + off]
                    b_line = B[b0 + off]
                    sim = _line_similarity(a_line, b_line, use_line_levenshtein_)
                    score += sim
                    if verbose:
                        logger.debug(
                            "%s:     pair  %s[%d] ~ %s[%d] -> +%.4f  (%r  vs  %r)",
                            label,
                            A_origin,
                            a0 + off,
                            B_origin,
                            b0 + off,
                            sim,
                            _short(a_line),
                            _short(b_line),
                        )
            else:
                # insert/delete during alignment contribute 0
                if verbose:
                    logger.debug(
                        "%s:   %s %s[%d:%d] / %s[%d:%d] -> +0.0",
                        label,
                        tag,
                        A_origin,
                        a0,
                        a1,
                        B_origin,
                        b0,
                        b1,
                    )

        if verbose:
            logger.debug("%s: Align score -> +%.4f", label, score)
        return score

    if R == R_hat:
        if verbose:
            logger.debug("Early return: R == R_hat -> score=1.0")
        return 1.0

    base_lines: list[str] = _remove_empty_lines(O)
    R_lines: list[str] = _remove_empty_lines(R)
    R_hat_lines: list[str] = _remove_empty_lines(R_hat)

    # Opcodes
    O_vs_R = _opcodes(base_lines, R_lines)
    O_vs_R_hat = _opcodes(base_lines, R_hat_lines)

    # Union of changed base intervals
    merged_union_intervals = _merged_union_change_intervals(O_vs_R, O_vs_R_hat)

    if verbose:
        logger.debug(
            "Base length (filtered)=%d, R length (filtered)=%d, R_hat length (filtered)=%d",
            len(base_lines),
            len(R_lines),
            len(R_hat_lines),
        )
        logger.debug("Merged union intervals (base indices): %s", merged_union_intervals)

    for union_start, union_end in merged_union_intervals:
        if verbose:
            logger.debug(
                "Union block: base[%d:%d] (len=%d)", union_start, union_end, union_end - union_start
            )

        # Per-base-line pass (denom + mutual-deletes)
        for i in range(union_start, union_end):
            R_piece_idx = _project_base_subrange_to_target_with_indices(
                O_vs_R, R_lines, i, i + 1
            )
            R_hat_piece_idx = _project_base_subrange_to_target_with_indices(
                O_vs_R_hat, R_hat_lines, i, i + 1
            )

            denom_add = max(1, len(R_piece_idx), len(R_hat_piece_idx))
            comps.denominator_base += denom_add

            if verbose:
                o_line = base_lines[i] if 0 <= i < len(base_lines) else ""
                logger.debug(
                    "  denom_base: base line O[%d]=%r -> R_piece=%s, R_hat_piece=%s => +%d",
                    i,
                    _short(o_line),
                    _fmt_indexed(R_piece_idx),
                    _fmt_indexed(R_hat_piece_idx),
                    denom_add,
                )

            if not R_piece_idx and not R_hat_piece_idx:
                comps.numerator_base_mutual_deletes += 1.0
                if verbose:
                    logger.debug(
                        "  num_mutual_delete: base line O[%d] deleted/compressed by BOTH -> +1.0",
                        i,
                    )

        # Whole-block content alignment
        R_full = _project_base_subrange_to_target(O_vs_R, R_lines, union_start, union_end)
        R_hat_full = _project_base_subrange_to_target(
            O_vs_R_hat, R_hat_lines, union_start, union_end
        )

        align_label = f"  num_block_align: base[{union_start}:{union_end}]"
        block_score = (
            _aligned_block_score_verbose(
                R_full,
                R_hat_full,
                label=align_label,
                A_origin="R",
                B_origin="R_hat",
                use_line_levenshtein_=use_line_levenshtein,
            )
            if verbose
            else _aligned_block_score(R_full, R_hat_full, use_line_levenshtein)
        )
        comps.numerator_base_block_align += block_score
        if verbose:
            logger.debug("%s -> +%.4f", align_label, block_score)

    # Insertions (slot union)
    R_insertions_by_slot = _build_insertions_map(O_vs_R, R_lines)
    R_hat_insertions_by_slot = _build_insertions_map(O_vs_R_hat, R_hat_lines)

    if verbose:
        R_ins_idx = _build_insertions_map_with_indices(O_vs_R, R_lines)
        R_hat_ins_idx = _build_insertions_map_with_indices(O_vs_R_hat, R_hat_lines)
    else:
        R_ins_idx = {}
        R_hat_ins_idx = {}

    for slot in set(R_insertions_by_slot) | set(R_hat_insertions_by_slot):
        ins_R = R_insertions_by_slot.get(slot, [])
        ins_R_hat = R_hat_insertions_by_slot.get(slot, [])

        denom_add = max(len(ins_R), len(ins_R_hat))
        comps.denominator_insertions += denom_add

        if verbose:
            logger.debug(
                "Insert slot %d: denom_insertions -> ins_R=%s, ins_R_hat=%s => +%d",
                slot,
                _fmt_indexed(R_ins_idx.get(slot, [])),
                _fmt_indexed(R_hat_ins_idx.get(slot, [])),
                denom_add,
            )

        align_label = f"  num_insert_align: slot={slot}"
        ins_score = (
            _aligned_block_score_verbose(
                ins_R,
                ins_R_hat,
                label=align_label,
                A_origin="R(ins)",
                B_origin="R_hat(ins)",
                use_line_levenshtein_=use_line_levenshtein,
            )
            if verbose
            else _aligned_block_score(ins_R, ins_R_hat, use_line_levenshtein)
        )
        comps.numerator_insertions += ins_score
        if verbose:
            logger.debug("%s -> +%.4f", align_label, ins_score)

    total_denominator = comps.denominator_base + comps.denominator_insertions
    if total_denominator == 0:
        if verbose:
            logger.debug("Degenerate: no changes anywhere -> score=1.0 (denominator=0)")
        return 1.0

    numerator_total = (
        comps.numerator_base_mutual_deletes
        + comps.numerator_base_block_align
        + comps.numerator_insertions
    )
    score = numerator_total / total_denominator
    score = max(0.0, min(1.0, score))

    if verbose:
        logger.debug(
            "Components: denom_base=%d denom_ins=%d num_mutual_del=%.4f num_block_align=%.4f num_ins=%.4f",
            comps.denominator_base,
            comps.denominator_insertions,
            comps.numerator_base_mutual_deletes,
            comps.numerator_base_block_align,
            comps.numerator_insertions,
        )
        logger.debug(
            "Final: numerator=%.4f denominator=%d score=%.6f",
            numerator_total,
            total_denominator,
            score,
        )

    return score
