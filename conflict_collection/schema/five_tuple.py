from typing import Optional

from conflict_parser import MergeMetadata
from pydantic import BaseModel


class Conflict5Tuple(BaseModel):
    """
    Merge Conflict represented in a 5-tuple structure.
    Contains the 5 necessary versions of a conflicting file (A, B, O, M, R).
    """

    ours_content: str
    """(A) Content of the 'ours' version in the merge conflict."""

    theirs_content: str
    """(B) Content of the 'theirs' version in the merge conflict."""

    base_content: Optional[str]
    """(O) Content of the 'base' version in the merge conflict.

    NOTE: In case of diverging history merges, this content may be a virtual base.
    Git defaults to creating a virtual base, an amalgamation of all qualifying bases,
    in case of multiple base merges.

    NOTE: Virtual bases do NOT match any single committed version.
    """

    conflict_content: str
    """(M) Content of the merge conflict, expected to include conflict markers."""

    resolved_content: Optional[str]
    """(R) Content of the resolved merge conflict."""

    merge_config: MergeMetadata
    """Configurations used for this merge conflict.

    Reference [Git - merge-config Documentation](https://git-scm.com/docs/merge-config#Documentation/merge-config.txt-mergeconflictStyle)
    """
