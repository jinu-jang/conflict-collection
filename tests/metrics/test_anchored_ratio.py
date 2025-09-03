import pytest

from conflict_collection.metrics.anchored_ratio import anchored_ratio


def _is_about(value, target, tol=1e-6):
    return abs(value - target) <= tol


# ──────────────────────────────────────────────────────────────────────────────
# 1) No changes anywhere → denom=0 ⇒ score defined as 1.0
#    Δ_R = ∅, Δ_R̂ = ∅ ; A_R = ∅, A_R̂ = ∅
#    Expected: 0 ÷ 0 → 1.0
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_no_changes_returns_one():
    O = "a\nb\nc"
    R = "a\nb\nc"
    R_hat = "a\nb\nc"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    assert score == 1.0, "Expected 0 ÷ 0 → 1.0 when no one changes anything"


# ──────────────────────────────────────────────────────────────────────────────
# 2) Only R changes one base line; R̂ leaves it as in O
#    Δ_R = {line2}, Δ_R̂ = ∅ ; insertions: none
#    Denominator = |Δ_R ∪ Δ_R̂| = 1
#    Numerator = exact matches on changed region = 0
#    Expected: 0 ÷ 1
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_one_side_changes_only():
    O = "a\nb\nc"
    R = "a\nB\nc"
    R_hat = "a\nb\nc"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 0 / 1
    assert _is_about(score, expected), f"Expected 0 ÷ 1 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 3) Pure insertions, same slot, identical content
#    Δ_R = Δ_R̂ = ∅ ; A_R(1) = A_R̂(1) = ['X','Y']  (slot after first line)
#    Denominator = max(2,2) = 2
#    Numerator   = exact equal lines in that slot = 2
#    Expected: 2 ÷ 2
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_pure_insertions_identical_same_slot():
    O = "L1\nL2"
    R = "L1\nX\nY\nL2"
    R_hat = "L1\nX\nY\nL2"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 2
    assert _is_about(score, expected), f"Expected 2 ÷ 2 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 4) Pure insertions, different slots, identical lists
#    Δ_R = Δ_R̂ = ∅ ; A_R(1) = ['X','Y'], A_R̂(2) = ['X','Y']
#    Denominator = max(2,0) + max(0,2) = 4
#    Numerator   = per-slot alignment only (different slots) → 0 + 0 = 0
#    Expected: 0 ÷ 4
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_pure_insertions_different_slots_no_credit():
    O = "L1\nL2\nL3"
    R = "L1\nX\nY\nL2\nL3"  # insert at slot 1
    R_hat = "L1\nL2\nX\nY\nL3"  # insert at slot 2
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 0 / 4
    assert _is_about(score, expected), f"Expected 0 ÷ 4 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 5) Expansion vs compression on the same base line
#    Δ_R = Δ_R̂ = {line B}
#    R(B) = ['X','Y','Z'], R̂(B) = ['X','W']
#    Denominator = max(|{B}|=1, 3, 2) = 3
#    Numerator   = exact alignment across slices = 1 ('X')
#    Expected: 1 ÷ 3
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_expansion_vs_compression_same_region():
    O = "A\nB\nC"
    R = "A\nX\nY\nZ\nC"
    R_hat = "A\nX\nW\nC"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 3
    assert _is_about(score, expected), f"Expected 1 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 6) Overlapping changes with containment + equal insertion
#    Rename of user's "complex" case for clarity.
#
#    Design (using 0-based base indices):
#      Δ_R     = [1,4)       (R replaces lines 1..3)
#      Δ_R̂    = [1,3)       (R̂ replaces lines 1..2)  ⇒  Δ_R ⊃ Δ_R̂
#      Insert  : A_R(end) = A_R̂(end) = {'line66'}     ⇒  equal insertion
#
#    Denominator (base):
#      micro pieces from boundaries {1,3,4}:
#        [1,3): max(2, len(R[1:3]->['line222','line233']), len(R̂[1:3]->['line45','line211','line333'])) = 3
#        [3,4): max(1, len(R->['line333','line444']),       len(R̂->['line4']))                         = 2
#      base total = 3 + 2 = 5
#    Denominator (insertions): end slot max(1,1) = 1
#    Denominator TOTAL = 6
#
#    Numerator:
#      base whole-block alignment: exactly one common equal line 'line333' = 1
#      insertions: 'line66' == 'line66' = 1
#      TOTAL = 2
#
#    Expected: 2 ÷ 6
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_contained_change_equal_insertion():
    O = "\n".join(
        [
            "line0",
            "line1",
            "line2",
            "line3",
            "line4",
        ]
    )
    R = "\n".join(
        [
            "line0",
            "line111",
            "line122",
            "line222",
            "line333",
            "line4",
            "line55",
        ]
    )
    R_hat = "\n".join(
        [
            "line0",
            "line34",
            "line100",
            "line222",
            "line3",
            "line4",
            "line55",
        ]
    )
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 6
    assert _is_about(score, expected), f"Expected 2 ÷ 6 = {expected}, got {score}"

    granular_score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        2 / 6 <= granular_score <= 1
    ), f"Using Levenshtein, expected score in [2/6, 1], got {granular_score}"


# ──────────────────────────────────────────────────────────────────────────────
# 7) Overlap with partial intersection (Δ_R ∩ Δ_R̂ ≠ ∅) and a single shared token
#    Base: a1 a2 a3 a4 a5 a6 a7
#    R   : replace [1,5) with ['b2','b3','KEEP','b5']; rest equal
#    R̂  : replace [3,7) with ['c4','KEEP','c6','c7']; rest equal
#
#    Δ_R = [1,5), Δ_R̂ = [3,7) ⇒ merged union [1,7)
#    Denominator (base): micro boundaries {1,3,5,7}:
#      [1,3): max(2,2,2)=2; [3,5): max(2,2,2)=2; [5,7): max(2,2,2)=2 ⇒ 6
#    Insertions: none
#    Numerator: whole-block alignment has exactly one equal line 'KEEP' ⇒ 1
#    Expected: 1 ÷ 6
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_overlap_partial_shared_line_only():
    O = "\n".join([f"a{i}" for i in range(1, 8)])
    R = "\n".join(["a1", "b2", "b3", "KEEP", "b5", "a6", "a7"])
    R_hat = "\n".join(["a1", "a2", "a3", "c4", "KEEP", "c6", "c7"])
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 6
    assert _is_about(score, expected), f"Expected 1 ÷ 6 = {expected}, got {score}"

    granular_score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        1 / 6 <= granular_score <= 2 / 6
    ), f"Using Levenshtein, expected score in [1/6, 2/6], got {granular_score}"


def test_anchored_ratio_one_overlaps_two():
    O = "\n".join([f"a{i}" for i in range(1, 8)])
    R = "\n".join(["a1", "b2", "b3", "KEEP", "b5", "a6", "b7"])
    R_hat = "\n".join(["a1", "a2", "a3", "c4", "KEEP", "c6", "c7"])
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 6
    assert _is_about(score, expected), f"Expected 1 ÷ 6 = {expected}, got {score}"

    granular_score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        1 / 6 <= granular_score <= 2 / 6
    ), f"Using Levenshtein, expected score in [1/6, 2/6], got {granular_score}"


def test_anchored_ratio_chained_overlap():
    O = "\n".join([f"a{i}" for i in range(1, 10)])
    R = "\n".join(["a1", "b2", "b3", "KEEP", "b5", "a6", "a7", "b8", "b9"])
    R_hat = "\n".join(["a1", "a2", "a3", "c4", "KEEP", "c6", "c7", "a8", "a9"])
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    assert score == 1 / 8


# ──────────────────────────────────────────────────────────────────────────────
# 8) Identical reorder across R and R̂ (both swap the same two lines)
#    Δ_R = Δ_R̂ = [1,3) and R[1,3)=R̂[1,3)=['l3','l2']
#    Denominator = max(2,2,2) = 2
#    Numerator   = equal block length = 2
#    Expected: 2 ÷ 2
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_identical_reorder_counts_as_full_match():
    O = "l1\nl2\nl3"
    R = "l1\nl3\nl2"
    R_hat = "l1\nl3\nl2"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 2
    assert _is_about(score, expected), f"Expected 2 ÷ 2 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 9) Different reorder vs unchanged
#    Δ_R = [1,3), Δ_R̂ = ∅
#    Denominator = max(2,2,2)=2
#    Numerator   = no equal block across slices ('l3,l2' vs 'l2,l3') with exact-only → 0
#    Expected: 0 ÷ 2
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_reorder_vs_unchanged_no_credit_without_levenshtein():
    O = "l1\nl2\nl3"
    R = "l1\nl3\nl2"
    R_hat = "l1\nl2\nl3"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 0 / 2
    assert _is_about(score, expected), f"Expected 0 ÷ 2 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# 10) Two disjoint base changes; one matches across R/R̂, the other does not
#     Δ_R = Δ_R̂ = {line2, line4}
#     At line2: R and R̂ both 'X'  → +1 numerator
#     At line4: R='Y', R̂='Z'      → +0 numerator
#     Denominator = 1 + 1 = 2
#     Expected: 1 ÷ 2
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_two_disjoint_regions_partial_agreement():
    O = "l1\nl2\nl3\nl4"
    R = "l1\nX\nl3\nY"
    R_hat = "l1\nX\nl3\nZ"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 2
    assert _is_about(score, expected), f"Expected 1 ÷ 2 = {expected}, got {score}"

    granular_score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        1 / 2 <= granular_score <= 1
    ), f"Using Levenshtein, expected score in [1/2, 1], got {granular_score}"


# ──────────────────────────────────────────────────────────────────────────────
# 11) User’s earlier “basic_3” (pure insertions: one common slot, one only R̂)
#     Δ_R = Δ_R̂ = ∅
#     A_R(end)   = {'line66'}
#     A_R̂(0)    = {'line45'},  A_R̂(end) = {'line66'}
#     Denominator = max(0,1) + max(1,1) = 2
#     Numerator   = 0 (top slot) + 1 (end slot) = 1
#     Expected: 1 ÷ 2
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_pure_insertions_one_common_one_unique():
    O = "line1\n" "line2\n" "line3\n" "line4\n" "line5\n"
    R = "line1\n" "line2\n" "line3\n" "line4\n" "line5\n" "line66\n"
    R_hat = (
        "line1\n"
        "line45\n"  # unique insertion at top
        "line2\n"
        "line3\n"
        "line4\n"
        "line5\n"
        "line66\n"  # common insertion at end
    )
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 2
    assert _is_about(score, expected), f"Expected 1 ÷ 2 = {expected}, got {score}"

    granular_score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        1 / 2 <= granular_score <= 1
    ), f"Using Levenshtein, expected score in [1/2, 1], got {granular_score}"


def test_anchored_ratio_empty_lines_are_ignored_1():
    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "managementscriptingtools.resources|PASS3 \\\n\n"
        "managementscriptingtools-gc|PASS3 \\\n\n"
        "sharedlibraries|PASS3 \\\n\n"
        "sharedlibraries.resources|PASS3 \\\n\n"
        "sharedlibrariesfeature|PASS3 \\\n\n"
        "webserver-events|PASS3 \\\n\n"
        "webserver-events.resources|PASS3 \\\n\n"
        "unpackx86csineutralrepository|PASS3 \\\n\n"
        "unpackx86csiresourcerepositories|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-events|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-servercommon|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-servercommon.resources|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "something-long-setup-keep-this-line-managementscriptingtools-deployment|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "managementscriptingtools-gc|PASS3 \\\n\n"
        "managementscriptingtools.resources|PASS3 \\\n\n"
        "sharedlibraries|PASS3 \\\n\n"
        "sharedlibraries.resources|PASS3 \\\n\n"
        "sharedlibrariesfeature|PASS3 \\\n\n"
        "webserver-events|PASS3 \\\n\n"
        "webserver-events.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "unpackx86csineutralrepository|PASS3 \\\n\n"
        "unpackx86csiresourcerepositories|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-events|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-servercommon|PASS3 \\\n\n"
        "servercommon\\sharedlibraries-servercommon.resources|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n"
        "something-long-setup-keep-this-line-managementscriptingtools-deployment|PASS3 \\\n"
        "managementscriptingtools|PASS3 \\\n"
        "managementscriptingtools-gc|PASS3 \\\n"
        "managementscriptingtools.resources|PASS3 \\\n"
        "sharedlibraries|PASS3 \\\n"
        "sharedlibraries.resources|PASS3 \\\n"
        "sharedlibrariesfeature|PASS3 \\\n"
        "webserver-events|PASS3 \\\n"
        "webserver-events.resources|PASS3 \\\n"
        "configuration.apphostfileprovider|PASS3 \\\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n"
        "unpackx86csineutralrepository|PASS3 \\\n"
        "unpackx86csiresourcerepositories|PASS3 \\\n"
        "servercommon\\sharedlibraries-events|PASS3 \\\n"
        "servercommon\\sharedlibraries-servercommon|PASS3 \\\n"
        "servercommon\\sharedlibraries-servercommon.resources|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 1.0, "Expected 6 ÷ 6 → 1.0 when all changes are the same"


def test_anchored_ratio_delete_vs_edit_1():
    """
    Delete 3 lines vs. edits same 3 lines
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Edits 3 lines after this line
        "configuration.apphostfileprovider-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg-edit|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 0.0, "Expected 0 ÷ 3 → 0.0 no same edits"


def test_anchored_ratio_delete_vs_edit_2():
    """
    Delete 3 lines vs. edit 1 of those 3 lines
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Edits 1 line after this line
        "configuration.apphostfileprovider-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 0.0, "Expected 0 ÷ 3 → 0.0 no same edits"


def test_anchored_ratio_delete_vs_edit_3():
    """
    Delete 3 lines vs. edit 1 middle line in those 3 lines
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Edits 1 line after this line
        "configuration.apphostfileprovider-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 0.0, "Expected 0 ÷ 3 → 0.0 no same edits"


def test_anchored_ratio_delete_vs_edit_4():
    """
    Delete 3 lines vs. edit 2 lines in a row in those 3 lines
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"  # Edits 2 line after this line
        "configuration.apphostfileprovider.resources-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg-edit|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 0.0, "Expected 0 ÷ 3 → 0.0 no same edits"


def test_anchored_ratio_delete_vs_edit_5():
    """
    Delete 3 lines vs. edit 2 non consecutive lines in those 3 lines
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider-edit|PASS3 \\\n\n"  # Edits 2 line after this line
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg-edit|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert score == 0.0, "Expected 0 ÷ 3 → 0.0 no same edits"


def test_anchored_ratio_delete_vs_edit_6():
    """
    Delete 3 lines vs. edit 2 lines and delete 1 middle line
    """

    O = (
        "BUILD_PASS3_CONSUMES= \\\n\n"
        "configuration.apphostfileprovider|PASS3 \\\n\n"
        "configuration.apphostfileprovider.resources|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Delete 3 lines after this line.
        "managementscriptingtools|PASS3 \\\n\n"
        "\n\n"
    )

    R_hat = (
        "BUILD_PASS3_CONSUMES= \\\n\n"  # Edit, delete, edit after this line
        "configuration.apphostfileprovider-edit|PASS3 \\\n\n"
        "configuration.apphostfileprovider-comreg-edit|PASS3 \\\n\n"
        "managementscriptingtools|PASS3 \\"
    )

    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert (
        score == 1 / 3
    ), "Expected 1 ÷ 3 → 0.3333. 1 same delete out of 3 changed lines"


# ──────────────────────────────────────────────────────────────────────────────
# A) Mutual deletes via delete vs compression (2/3 numerator)
#    R deletes 3 lines; R̂ compresses those 3 base lines into 1 line.
#    Mutual-delete credit on two of the three base lines (first two slices empty).
#    Denominator (base)=3, Numerator (base)=2 → 2/3
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_mutual_deletes_via_compression_vs_delete_2_of_3():
    O = "A\nB\nC\nD\nE"
    R = "A\nE"  # delete B,C,D
    R_hat = "A\nX\nE"  # replace B,C,D with single 'X' (compression)
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 3
    assert _is_about(score, expected), f"Expected 2 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# C) Two shared equal lines inside the changed block, shifted in order
#    Whole-block alignment finds 'K1' and 'K2' => numerator 2; denom 3 => 2/3
# ──────────────────────────────────────────────────────────────────────────────
@pytest.mark.skip(reason="Potentially wanted behavior, needs further discussion")
def test_anchored_ratio_two_shared_lines_shifted_inside_block():
    O = "a0\na1\na2\na3\na4"
    R = "a0\nK1\nX\nK2\na4"  # replace [1,4) -> [K1, X, K2]
    R_hat = "a0\nK1\nK2\nY\na4"  # replace [1,4) -> [K1, K2, Y]
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 3
    assert _is_about(score, expected), f"Expected 2 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# D) Insertions in the same slot with one side having an extra trailing line
#    Insertion denom = max(3,2)=3; insertion numerator = 2 (I1, I2) -> 2/3
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_insertions_same_slot_extra_trailing():
    O = "A\nB"
    R = "A\nI1\nI2\nI3\nB"
    R_hat = "A\nI1\nI2\nB"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 3
    assert _is_about(score, expected), f"Expected 2 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# F) Duplicates inside the block: LCS/SequenceMatcher should match two items
#    R: [K, X, K], R̂: [K, K, X] -> equal count 2 -> 2/3
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_duplicates_inside_block_count_both_matches():
    O = "a0\na1\na2\na3"
    R = "a0\nK\nX\nK"
    R_hat = "a0\nK\nK\nX"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 2 / 3
    assert _is_about(score, expected), f"Expected 2 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# G) Two disjoint union blocks; only the first has a shared equal line
#    Block1: [1,3) -> [K1, X] vs [K1, Y] => +1
#    Block2: [4,5) -> U vs V => +0
#    Denom = 2 + 1 = 3, Numerator = 1 -> 1/3
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_two_union_blocks_only_one_matches():
    O = "A\nB\nC\nD\nE\nF"
    R = "A\nK1\nX\nD\nU\nF"  # [1,3)->[K1,X], [4,5)->[U]
    R_hat = "A\nK1\nY\nD\nV\nF"  # [1,3)->[K1,Y], [4,5)->[V]
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=False)
    expected = 1 / 3
    assert _is_about(score, expected), f"Expected 1 ÷ 3 = {expected}, got {score}"


# ──────────────────────────────────────────────────────────────────────────────
# H) Levenshtein-only partial credit for a single edited line
#    Classic "kitten" vs "sitting" -> ratio ≈ 10/13 ≈ 0.7692 (numerator=that; denom=1)
# ──────────────────────────────────────────────────────────────────────────────
def test_anchored_ratio_levenshtein_partial_credit_single_line_edit():
    O = "a\nb\nc"
    R = "a\nkitten\nc"
    R_hat = "a\nsitting\nc"
    score = anchored_ratio(O, R, R_hat, use_line_levenshtein=True)
    assert _is_about(score, 0.6153, tol=1e-4), f"Expected ~0.6153, got {score}"
