from dataclasses import dataclass
from typing import Literal, Union

DELETE_TOKEN = "‽DELETED‽"
"""Indicate that a file was deleted in a commit.
Interrobang punctuation is used to avoid confusion with real file contents."""

T_ALL_CONFLICT_TYPES = Literal[
    "modify_modify",
    "added_by_us",
    "added_by_them",
    "delete_modify",
    "modify_delete",
    "delete_delete",
    "add_add",
]
ALL_CONFLICT_TYPES = [
    "modify_modify",
    "added_by_us",
    "added_by_them",
    "delete_modify",
    "modify_delete",
    "delete_delete",
    "add_add",
]


@dataclass(slots=True, frozen=True)
class ModifyModifyConflictCase:
    """Represents a single merge conflict case with all relevant file contents."""

    base_path: str
    ours_path: str
    theirs_path: str

    base_content: str
    ours_content: str
    theirs_content: str

    conflict_path: str
    conflict_body: str

    resolved_path: str | None
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["modify_modify"] = "modify_modify"


@dataclass(slots=True, frozen=True)
class AddedByUsConflictCase:
    """Represents a merge conflict where the base file has been added on our side but conflicts.

    Potentially one of the rarest forms of merge conflicts.
    From the human perspective it happens when one side adds a new file,
    but the other side moved the directory the file was added to,
    and then something goes wrong with the merge.

    Git will show this as an "added by us" conflict.
    """

    base_path: None
    ours_path: str
    theirs_path: None

    base_content: None
    ours_content: str
    theirs_content: None

    conflict_path: str
    conflict_body: str
    """The contents of this file will NOT contain conflict markers,
    because it is a new file that was added in one side."""

    resolved_path: str | None
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["added_by_us"] = "added_by_us"


@dataclass(slots=True, frozen=True)
class AddedByThemConflictCase:
    """Represents a merge conflict where the base file has been added on their side but conflicts.

    Potentially one of the rarest forms of merge conflicts.
    From the human perspective it happens when one side adds a new file,
    but the other side moved the directory the file was added to,
    and then something goes wrong with the merge.

    Git will show this as an "added by them" conflict.
    """

    base_path: None
    ours_path: None
    theirs_path: str

    base_content: None
    ours_content: None
    theirs_content: str

    conflict_path: str
    conflict_body: str
    """The contents of this file will NOT contain conflict markers,
    because it is a new file that was added in one side."""

    resolved_path: str | None
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["added_by_them"] = "added_by_them"


@dataclass(slots=True, frozen=True)
class DeleteModifyConflictCase:
    """Represents a merge conflict where the base file has been deleted from our side,
    and modified on their branch."""

    base_path: str
    ours_path: None
    theirs_path: str

    base_content: str
    ours_content: None
    theirs_content: str

    conflict_path: str
    """As our content is deleted, this is just base_path."""
    conflict_body: str

    resolved_path: str | None
    """The resolution may be a deleted file, in which case this is None."""
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["delete_modify"] = "delete_modify"


@dataclass(slots=True, frozen=True)
class ModifyDeleteConflictCase:
    """Represents a merge conflict where the base file has been deleted from their side,
    and modified on our branch."""

    base_path: str
    ours_path: str
    theirs_path: None

    base_content: str
    ours_content: str
    theirs_content: None

    conflict_path: str
    """As their content is deleted, this is just ours_path."""
    conflict_body: str

    resolved_path: str | None
    """The resolution may be a deleted file, in which case this is None."""
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["modify_delete"] = "modify_delete"


@dataclass(slots=True, frozen=True)
class DeleteDeleteConflictCase:
    """Represents a merge conflict where the base file has been deleted from both sides.
    From the human perspective, this happens when there's a rename-rename.
    Git will show this as a delete-delete conflict, followed by an add by us and an add by them.
    """

    base_path: str
    ours_path: None
    theirs_path: None

    base_content: str
    ours_content: None
    theirs_content: None

    conflict_path: str
    """In the delete-delete case, this is just base_path."""
    conflict_body: None

    resolved_path: None
    resolved_body: None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["delete_delete"] = "delete_delete"


@dataclass(slots=True, frozen=True)
class AddAddConflictCase:
    """Represents a merge conflict where a file has been added in both branches.
    From the human perspective, this happens when there's a rename-rename.
    Git will show this as a delete-delete conflict, followed by an add by us and an add by them.

    NOTE: This conflict can generate two conflicting files with the same content in two different paths.
    """

    base_path: None
    ours_path: str
    theirs_path: str

    base_content: None
    ours_content: str
    theirs_content: str

    conflict_path: str
    """In the add-add case, this is our path."""
    conflict_body: str
    """The content of the file as it exists in the working tree, with conflict markers."""

    resolved_path: str | None
    resolved_body: str | Literal["‽DELETED‽"] | None
    """The resolution may be a deleted file, in which case it will be the special DELETE_TOKEN."""

    conflict_type: Literal["add_add"] = "add_add"


ConflictCase = Union[
    DeleteDeleteConflictCase,
    AddedByUsConflictCase,
    AddedByThemConflictCase,
    ModifyDeleteConflictCase,
    DeleteModifyConflictCase,
    ModifyModifyConflictCase,
    AddAddConflictCase,
]
