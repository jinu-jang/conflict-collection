from conflict_parser import MergeMetadata
from git import Optional, Repo

from conflict_collection.collectors.conflict_type._git_ops import (
    group_conflict_families,
    read_blob,
    read_worktree_file,
)
from conflict_collection.schema.typed_five_tuple import (
    AddAddConflictCase,
    AddedByThemConflictCase,
    AddedByUsConflictCase,
    ConflictCase,
    DeleteDeleteConflictCase,
    DeleteModifyConflictCase,
    ModifyDeleteConflictCase,
    ModifyModifyConflictCase,
)


def collect(
    repo_path: str, resolution_sha: str, merge_config: Optional[MergeMetadata] = None
) -> list[ConflictCase]:
    """Collect typed merge conflict cases.

    Reads the raw unmerged index (``git ls-files -u``) and groups index stages
    (1=base, 2=ours, 3=theirs) into logical "conflict families". Each family
    is normalised into one of the dataclass variants from
    :mod:`conflict_collection.schema.typed_five_tuple`.

    Skips files that Git internally marks as conflicted but whose working tree
    contents no longer contain conflict markers (auto-resolved edge cases).

    Args:
        repo_path: Filesystem path to a Git repository currently in a merge-conflict state.
        resolution_sha: Commit SHA representing the resolved state (used to retrieve final blob content).
        merge_config: Optional merge metadata (used to validate marker size / style).

    Returns:
        List of typed ``ConflictCase`` instances.

    Raises:
        ValueError: If expected blobs/paths are missing for a detected conflict shape.
    """
    repo = Repo(repo_path)

    # 1. group by "conflict family", or loosely speaking "same file"
    groups = group_conflict_families(repo)

    cases: list[ConflictCase] = []

    # 3. build ConflictCase objects
    for slot in groups.values():
        found_stages = frozenset(slot.keys())

        o_blob, o_path = slot.get(1, (None, None))
        a_blob, a_path = slot.get(2, (None, None))
        b_blob, b_path = slot.get(3, (None, None))

        if found_stages == set({}):
            raise ValueError(
                "No blobs found in conflict group. "
                "This should not happen, please report a bug."
            )

        elif found_stages == {1}:
            if o_blob is None or o_path is None:
                raise ValueError(
                    "Delete-Delete conflict detected, but no base blob or path found. "
                    "This should not happen, please report a bug."
                )

            cases.append(
                DeleteDeleteConflictCase(
                    base_path=str(o_path),
                    ours_path=None,
                    theirs_path=None,
                    base_content=o_blob.data_stream.read().decode("utf-8", "replace"),
                    ours_content=None,
                    theirs_content=None,
                    conflict_path=str(o_path),
                    conflict_body=None,
                    resolved_path=None,
                    resolved_body=None,
                )
            )

        elif found_stages == {2}:
            if a_blob is None or a_path is None:
                raise ValueError(
                    "Added by us conflict detected, but no blob or path found. "
                    "This should not happen, please report a bug."
                )

            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(a_path))

            cases.append(
                AddedByUsConflictCase(
                    base_path=None,
                    ours_path=str(a_path),
                    theirs_path=None,
                    base_content=None,
                    ours_content=a_blob.data_stream.read().decode("utf-8", "replace"),
                    theirs_content=None,
                    conflict_path=str(a_path),
                    conflict_body=read_worktree_file(repo, str(a_path)),
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )

        elif found_stages == {3}:
            if b_blob is None or b_path is None:
                raise ValueError(
                    "Added by them conflict detected, but no blob or path found. "
                    "This should not happen, please report a bug."
                )

            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(b_path))

            cases.append(
                AddedByThemConflictCase(
                    base_path=None,
                    ours_path=None,
                    theirs_path=str(b_path),
                    base_content=None,
                    ours_content=None,
                    theirs_content=b_blob.data_stream.read().decode("utf-8", "replace"),
                    conflict_path=str(b_path),
                    conflict_body=read_worktree_file(repo, str(b_path)),
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )

        elif found_stages == {1, 2}:
            if a_blob is None or a_path is None:
                raise ValueError(
                    "Modify-Delete conflict detected, but no blob or path found. "
                    "This should not happen, please report a bug."
                )
            if o_blob is None or o_path is None:
                raise ValueError(
                    "Modify-Delete conflict detected, but no base blob or path found. "
                    "This should not happen, please report a bug."
                )

            # Figure out which branch was accepted
            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(a_path))

            ours_content = a_blob.data_stream.read().decode("utf-8", "replace")
            cases.append(
                ModifyDeleteConflictCase(
                    base_path=str(o_path),
                    ours_path=str(a_path),
                    theirs_path=None,
                    base_content=o_blob.data_stream.read().decode("utf-8", "replace"),
                    ours_content=ours_content,
                    theirs_content=None,
                    conflict_path=str(a_path),
                    conflict_body=ours_content,
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )

        elif found_stages == {1, 3}:
            if b_blob is None or b_path is None:
                raise ValueError(
                    "Delete-Modify conflict detected, but no blob or path found. "
                    "This should not happen, please report a bug."
                )
            if o_blob is None or o_path is None:
                raise ValueError(
                    "Delete-Modify conflict detected, but no base blob or path found. "
                    "This should not happen, please report a bug."
                )

            # Figure out which branch was accepted
            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(b_path))

            theirs_content = b_blob.data_stream.read().decode("utf-8", "replace")
            cases.append(
                DeleteModifyConflictCase(
                    base_path=str(o_path),
                    ours_path=None,
                    theirs_path=str(b_path),
                    base_content=o_blob.data_stream.read().decode("utf-8", "replace"),
                    ours_content=None,
                    theirs_content=theirs_content,
                    conflict_path=str(b_path),
                    conflict_body=theirs_content,
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )
            continue

        elif found_stages == {2, 3}:
            if a_blob is None or a_path is None or b_blob is None or b_path is None:
                raise ValueError(
                    "Add-Add conflict detected, but not all blobs or paths are present. "
                    "This should not happen, please report a bug."
                )

            # Figure out which branch was accepted
            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(a_path))
            if resolved_path is None:
                resolved_path, resolved_body = read_blob(
                    repo, resolution_sha, str(b_path)
                )

            cases.append(
                AddAddConflictCase(
                    base_path=None,
                    ours_path=str(a_path),
                    theirs_path=str(b_path),
                    base_content=None,
                    ours_content=a_blob.data_stream.read().decode("utf-8", "replace"),
                    theirs_content=b_blob.data_stream.read().decode("utf-8", "replace"),
                    conflict_path=str(a_path),
                    conflict_body=read_worktree_file(repo, str(a_path)),
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )
            continue

        else:
            if (
                o_blob is None
                or a_blob is None
                or b_blob is None
                or o_path is None
                or a_path is None
                or b_path is None
            ):
                raise ValueError(
                    "Modify-Modify conflict detected, but not all blobs or paths are present. "
                    "This should not happen, please report a bug."
                )

            resolved_path, resolved_body = read_blob(repo, resolution_sha, str(a_path))
            conflict_body = read_worktree_file(repo, str(a_path))
            expected_header = "<" * (
                7 if merge_config is None else merge_config.marker_size
            )
            if (
                not conflict_body.startswith(expected_header)
                and ("\n" + expected_header) not in conflict_body
            ):
                # If the conflict markers are not present, we assume the file was auto-resolved.
                # NOTE: Refer to the bug explained in group_conflict_families() function.
                continue

            cases.append(
                ModifyModifyConflictCase(
                    base_path=str(o_path),
                    ours_path=str(a_path),
                    theirs_path=str(b_path),
                    base_content=o_blob.data_stream.read().decode("utf-8", "replace"),
                    ours_content=a_blob.data_stream.read().decode("utf-8", "replace"),
                    theirs_content=b_blob.data_stream.read().decode("utf-8", "replace"),
                    conflict_path=str(a_path),
                    conflict_body=conflict_body,
                    resolved_path=resolved_path,
                    resolved_body=resolved_body,
                )
            )

    return cases
