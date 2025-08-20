from collections import defaultdict
from pathlib import Path

from git import Blob, GitCommandError, Repo, StageType


def list_tracked_files(repo: Repo) -> list[str]:
    """Files at HEAD (ignores unstaged/untracked)."""
    return repo.git.ls_files().splitlines()


def _git_error_file_not_found(e: GitCommandError) -> bool:
    """
    Check if the GitCommandError is due to a file not found.
    This is used to determine if we should return SPECIAL_DELETE_TOKEN.
    """
    return e.status == 128 and (
        "not found" in e.stderr or "exists on disk, but not in " in e.stderr
    )


def read_blob(repo: Repo, commit: str, path: str):
    """
    File *inside* a commit.
    Returns None when the file does not exist in that commit.
    """
    data: str

    try:
        # Use git show to get the file content at a specific commit
        data = repo.git.show(f"{commit}:{path}")
    except GitCommandError as e:
        if _git_error_file_not_found(e):
            return None, None
        else:
            raise e

    return path, data


def read_worktree_file(repo: Repo, path: str):
    """File as it exists in the working tree (e.g. with conflict markers)."""
    if not repo.working_tree_dir:
        raise ValueError("Repository is not checked out")

    fp = Path(repo.working_tree_dir) / path
    return fp.read_text(encoding="utf-8", errors="replace")


def group_conflict_families(repo: Repo):
    """Group conflict cases by their logical family.
    Logical family is loosely defined as which "file" the conflict is about.

    NOTE: Due to an unexplainable GitPython bug,
    `git diff --name-only --diff-filter=U` returns all files including those
    that can be auto-resolved.
    Hence there is no way to filter out those files here.
    """
    # 1. normalise index rows
    rows: list[tuple[StageType, Blob, Path]] = []
    for path, entry_list in repo.index.unmerged_blobs().items():
        # patch in the path because GitPython omits it inside each tuple
        for tpl in entry_list:
            rows.append((tpl[0], tpl[1], Path(path)))  # (stage, Blob, Path)

    # 2. group by "conflict family"
    groups: dict[str, dict[int, tuple[Blob, Path]]] = defaultdict(dict)
    for stage, blob, path in rows:
        family_key = None

        family_key = f"{blob.hexsha}:{path}"  # default key for stage 1

        if stage != 1:
            # Check if stage 1 row exists
            for key in groups:
                if key.startswith(blob.hexsha) or key.endswith(str(path)):
                    family_key = key

        groups[family_key][stage] = (blob, path)

    return groups
