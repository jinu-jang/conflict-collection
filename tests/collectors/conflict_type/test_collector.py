from pathlib import Path

from conflict_collection.collectors.conflict_type import collect


def test_no_exception_thrown_conflict_type_collection(conflict_repo_path: Path):
    """
    Very basic smoke test to see no exceptions arise from a simple conflict.
    """
    repo_path = str(conflict_repo_path)

    _ = collect(repo_path, "ce515764e7627081831e36617e8851ae4b8cd734")
