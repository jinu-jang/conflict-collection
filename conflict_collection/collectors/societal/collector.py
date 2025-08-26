"""Orchestrates collection of ownership & recency metrics for conflicted files."""

import logging
from typing import Iterable, Optional

from git import Repo

from conflict_collection.collectors.societal._git_ops import (
    age_days,
    blame_aggregate,
    commit_author_str,
    commit_epoch,
    conflicted_files,
    count_commits_by_author,
    count_commits_by_author_since_bases,
    integrator_name,
    last_commit_for_path,
    merge_bases,
    rev_parse,
)
from conflict_collection.schema.social_signals import (
    BlameEntry,
    IntegratorPriors,
    SocialSignalsRecord,
)


def collect(
    repo_path: str = ".",
    files: Optional[Iterable[str]] = None,
) -> dict[str, SocialSignalsRecord]:
    """
    Collect social-signal metrics for conflicted files (or explicit files).
    Returns a dictionary mapping from file path to SocialSignalsRecord.
    """
    repo = Repo(repo_path)

    file_list = list(files) if files else conflicted_files(repo)
    if not file_list:
        return {}

    head_sha = rev_parse(repo, "HEAD")
    merge_sha = rev_parse(repo, "MERGE_HEAD")
    base_shas = merge_bases(repo, head_sha, merge_sha)
    epoch_head = commit_epoch(repo, head_sha)
    epoch_merge = commit_epoch(repo, merge_sha)
    ref_ts = max(epoch_head, epoch_merge)

    integrator = integrator_name(repo)

    results: dict[str, SocialSignalsRecord] = {}
    """Mapping from file path to SocialSignalsRecord"""

    for f in file_list:
        ours_last = last_commit_for_path(repo, head_sha, f)
        theirs_last = last_commit_for_path(repo, merge_sha, f)
        if ours_last is None:
            logging.error(
                f"Last commit for {f} not found on {repo} "
                f"starting from commit hash {head_sha}. "
                "Skipping file."
            )
            continue
        if theirs_last is None:
            logging.error(
                f"Last commit for {f} not found on {repo} "
                f"starting from commit hash {merge_sha}. "
                "Skipping file."
            )
            continue

        ours_author = commit_author_str(ours_last)
        theirs_author = commit_author_str(theirs_last)

        owner_commits_ours = count_commits_by_author_since_bases(
            repo, f, ours_author, base_shas, head_sha
        )
        owner_commits_theirs = count_commits_by_author_since_bases(
            repo, f, theirs_author, base_shas, merge_sha
        )

        age_days_ours = age_days(ref_ts, ours_last)
        age_days_theirs = age_days(ref_ts, theirs_last)

        integrator_prev = (
            count_commits_by_author(repo, f, integrator) if integrator else 0
        )

        blame_pairs = blame_aggregate(repo, head_sha, f)
        blame_table = [BlameEntry(author=a, lines=n) for a, n in blame_pairs]

        results[f] = SocialSignalsRecord(
            file=f,
            ours_author=ours_author,
            theirs_author=theirs_author,
            owner_commits_ours=owner_commits_ours,
            owner_commits_theirs=owner_commits_theirs,
            age_days_ours=age_days_ours,
            age_days_theirs=age_days_theirs,
            integrator_priors=IntegratorPriors(resolver_prev_commits=integrator_prev),
            blame_table=sorted(blame_table, key=lambda b: b.lines, reverse=True),
        )

    return results
