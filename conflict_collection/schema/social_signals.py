"""Data models for social signals captured from a Git repository."""

from typing import List, Optional

from pydantic import BaseModel


class BlameEntry(BaseModel):
    author: str
    """Author name or email as attributed by `git blame`."""

    lines: int
    """Number of lines attributed to this author in the blamed revision."""


class IntegratorPriors(BaseModel):
    resolver_prev_commits: int
    """Number of prior commits by the current integrator touching this file."""


class SocialSignalsRecord(BaseModel):
    file: str
    """Repo-relative path to the conflicted file."""

    ours_author: Optional[str] = None
    """Author of the most recent commit touching this file on our side (HEAD)."""

    theirs_author: Optional[str] = None
    """Author of the most recent commit touching this file on their side (MERGE_HEAD)."""

    owner_commits_ours: int = 0
    """Count of commits authored by `ours_author` in `merge-base..HEAD` for this file."""

    owner_commits_theirs: int = 0
    """Count of commits authored by `theirs_author` in `merge-base..MERGE_HEAD` for this file."""

    age_days_ours: Optional[int] = None
    """Age in days of our most recent commit for this file (relative to the newer of HEAD/MERGE_HEAD)."""

    age_days_theirs: Optional[int] = None
    """Age in days of their most recent commit for this file (relative to the newer of HEAD/MERGE_HEAD)."""

    integrator_priors: IntegratorPriors
    """Per-integrator priors capturing local resolver behavior."""

    blame_table: List[BlameEntry]
    """Aggregated blame table at `HEAD`, grouped by author."""
