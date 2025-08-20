"""Thin Git helpers built on GitPython. Keeps subprocess-y details contained."""

import re
from collections import Counter
from typing import Iterable, List, Optional, Tuple

from git import Commit, GitCommandError, Repo


def conflicted_files(repo: Repo) -> List[str]:
    """Return a list of paths that are currently in a merge conflict state.

    Equivalent underlying git invocation:
        git diff --name-only --diff-filter=U

    Args:
        repo: A GitPython ``Repo`` object representing the repository.

    Returns:
        A list of file paths (relative to the repo root) that have unresolved
        merge conflicts (diff filter ``U``).
    """
    out = repo.git.diff("--name-only", "--diff-filter=U")
    return [p for p in out.splitlines() if p.strip()]


def rev_parse(repo: Repo, name: str) -> str:
    """Resolve a revision/name to a full commit SHA (like ``git rev-parse``).

    Args:
        repo: Repository handle.
        name: A ref name / revision expression acceptable to ``git rev-parse``
            (e.g. ``HEAD``, ``main``, ``HEAD~2``, an abbreviated SHA, etc.).

    Returns:
        The resolved full 40-character (or repository native) SHA string.
    """
    return repo.git.rev_parse(name).strip()


def merge_bases(repo: Repo, a: str, b: str) -> list[str]:
    """Return the merge base commit SHA for two revisions.

    Mirrors ``git merge-base <a> <b>`` and returns a list of all merge bases.

    Args:
        repo: Repository handle.
        a: First revision expression.
        b: Second revision expression.

    Returns:
        List of merge base SHA strings.
    """
    bases: List[Commit] = repo.merge_base(a, b) or []
    return [c.hexsha for c in bases]


def commit_epoch(repo: Repo, sha: str) -> int:
    """Get the commit's author/committer timestamp as a UNIX epoch (seconds)."""
    c = repo.commit(sha)
    return int(c.committed_date)


def last_commit_for_path(repo: Repo, rev: str, path: str) -> Optional[Commit]:
    """Return the most recent commit (at or before ``rev``) that touched ``path``.

    Args:
        repo: Repository handle.
        rev: Revision (single commit / ref) to start walking backwards from.
        path: File path to filter history by.

    Returns:
        The most recent ``Commit`` object touching ``path`` reachable from
        ``rev`` or ``None`` if not found / lookup fails.
    """
    try:
        commits: Iterable[Commit] = repo.iter_commits(rev, paths=path, max_count=1)
        return next(iter(commits), None)
    except GitCommandError:
        return None


def commit_author_str(commit: Commit) -> Optional[str]:
    """Extract a human-meaningful author identifier from a commit.

    Prefers the author's display name unless it is blank or the sentinel
    ``"not committed yet"`` (seen in some in-progress states), falling back to
    the email. Returns ``None`` for missing identity.

    Args:
        commit: A ``Commit`` or ``None``.

    Returns:
        Author name or email, or ``None`` if unavailable.
    """
    name = (commit.author.name or "").strip()
    email = (commit.author.email or "").strip()
    if name and name.lower() != "not committed yet":
        return name
    return email or None


def count_commits_by_author(repo: Repo, path: str, author: str) -> int:
    """Count prior commits on ``path`` authored by ``author``.

    Mirrors shell pattern: ``git log --pretty='%an' --author="$AUTHOR" -- <path> | wc -l``.

    Args:
        repo: Repository handle.
        path: File path to inspect.
        author: Author name to match; if ``None`` returns 0.

    Returns:
        Count of matching commits (0 on errors).
    """
    # Mirrors: git log --pretty='%an' --author="$author" -- "$f" | wc -l
    try:
        out = repo.git.log("--pretty=%an", f"--author={author}", "--", path)
        return len([ln for ln in out.splitlines() if ln.strip()])
    except GitCommandError:
        return 0


def count_commits_by_author_between(
    repo: Repo, path: str, author: str, a: str, b: str
) -> int:
    """Count commits by a given author that modified ``path`` in ``a..b``.

    The commit range semantics follow git's ``a..b``: excludes ``a`` itself,
    includes ``b`` if reachable. Filtering matches on the author name exactly
    (case sensitive) as produced by ``%an`` formatting.

    Args:
        repo: Repository handle.
        path: File path to restrict history.
        author: Exact author name to match (``%an``); if ``None`` returns 0.
        a: Lower bound revision (excluded).
        b: Upper bound revision (included if reachable).

    Returns:
        Integer count of matching commits.
    """
    # Range `a..b` (exclusive of a, inclusive of b)
    # We filter by author name like the bash script's %an + grep -Fxc.
    log = repo.git.log(f"{a}..{b}", "--pretty=%an", "--", path)
    names = [ln.strip() for ln in log.splitlines() if ln.strip()]
    return sum(1 for n in names if n == author)


def count_commits_by_author_since_bases(
    repo: Repo,
    path: str,
    author: Optional[str],
    bases: Iterable[str],
    tip: str,
    *,
    exact_name: bool = True,
    use_mailmap: bool = True,
    include_merges: bool = True,
    first_parent: bool = False,
    ancestry_path: bool = False,
) -> int:
    """Count commits by a given author that modified `path`, reachable from
    `tip` but from none of the given merge-bases.

    Conceptually equivalent to:
    `git log TIP ^MB1 ^MB2 ... -- PATH` — i.e., include commits on `tip`'s side
    that are not reachable from any merge-base (handles criss-cross / virtual-base
    merges correctly). If `bases` is empty, considers the entire history
    reachable from `tip`.

    Args:
        repo: Repository handle.
        path: File path to restrict history (passed to `git log -- PATH`).
        author: Author identity to match; if `None` returns 0. Matching uses
            `%aN` (mailmap-resolved) when `use_mailmap=True`, otherwise `%an`.
        bases: Iterable of merge-base revisions to exclude. Commits reachable from
            any element of `bases` are excluded.
        tip: Upper-bound revision whose reachable commits are considered (included
            if reachable and not excluded by any base).
        exact_name: If `True`, require an exact string match to the author name.
            If `False`, interpret `author` as a regular-expression pattern and
            apply a full-match against the author name.
        use_mailmap: If `True`, resolve identities via `.mailmap` and compare
            against `%aN`; if `False`, compare raw names from `%an`.
        include_merges: If `True`, include merge commits in the count; if
            `False`, exclude them (`--no-merges`).
        first_parent: If `True`, traverse only the first-parent chain of `tip`
            (`--first-parent`) to emphasize the branch's mainline.
        ancestry_path: If `True`, restrict to commits that lie on some ancestry
            path from any base to `tip` (`--ancestry-path`).

    Returns:
        Integer count of matching commits.
    """

    if not author:
        return 0

    rev_args: List[str] = []
    if first_parent:
        rev_args.append("--first-parent")
    if ancestry_path:
        rev_args.append("--ancestry-path")
    if not include_merges:
        rev_args.append("--no-merges")
    if use_mailmap:
        rev_args.append("--use-mailmap")

    # Build revision set: <tip> ^MB1 ^MB2 ...
    revs = [tip] + [f"^{mb}" for mb in bases]

    # %aN respects --use-mailmap; fallback to %an otherwise
    fmt = "%aN" if use_mailmap else "%an"
    out = repo.git.log(
        *rev_args,
        *revs,
        f"--pretty={fmt}",
        "--",
        path,
    )
    names = [ln.strip() for ln in out.splitlines() if ln.strip()]

    if exact_name:
        return sum(1 for n in names if n == author)
    else:
        # exact match on email may be better; for names, escape for regex
        pat = re.compile(re.escape(author))
        return sum(1 for n in names if pat.fullmatch(n) is not None)


def age_days(ref_ts: int, commit: Commit) -> int:
    """Compute the age (in whole days) of ``commit`` relative to ``ref_ts``.

    Args:
        ref_ts: Reference timestamp (UNIX seconds) usually 'now' or merge time.
        commit: Commit whose age to compute.

    Returns:
        Non-negative integer number of elapsed days, or ``None`` if commit is
        ``None``.
    """
    return max(0, (ref_ts - int(commit.committed_date)) // 86400)


def integrator_name(repo: Repo) -> Optional[str]:
    """Return the configured ``user.name`` (integrator) for the repository.

    Returns ``None`` if the config key is unset or retrieval errors.
    """
    try:
        name = repo.git.config("--get", "user.name").strip()
        return name or None
    except GitCommandError:
        return None


def blame_aggregate(repo: Repo, rev: str, path: str) -> List[Tuple[str, int]]:
    """
    Aggregate blame information by author for a given revision of a path.

    Equivalent git invocation:
        git blame -w --line-porcelain <rev> -- <path>

    Each line in the file (after whitespace-insensitive blame) contributes 1 to
    its associated author (preferring author name then email; falling back to
    "unknown" if neither is available).

    Args:
        repo: Repository handle.
        rev: Revision (commit SHA / ref) to blame.
        path: File path to blame.

    Returns:
        A list of ``(author, line_count)`` pairs. Order is not guaranteed.
    """
    try:
        txt = repo.git.blame("-w", "--line-porcelain", rev, "--", path)
    except GitCommandError:
        return []

    counts: Counter[str] = Counter()
    current_author: Optional[str] = None
    current_mail: Optional[str] = None

    for line in txt.splitlines():
        if line.startswith("author "):
            current_author = line[7:].strip()
        elif line.startswith("author-mail "):
            current_mail = line[len("author-mail ") :].strip()
            # Strip surrounding <...>
            if current_mail and "<" in current_mail and ">" in current_mail:
                current_mail = current_mail.split("<", 1)[1].split(">", 1)[0]
        elif line.startswith("\t"):
            author = (current_author or "").strip()
            if not author or author.lower() == "not committed yet":
                author = (current_mail or "").strip()
            if not author:
                author = "unknown"
            counts[author] += 1
            # Reset to avoid bleed across hunks
            current_author = None
            current_mail = None

    return list(counts.items())
