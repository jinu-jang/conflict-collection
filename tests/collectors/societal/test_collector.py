from pathlib import Path

from conflict_collection.collectors.societal import collect


def test_no_exception_thrown_societal_collection(conflict_repo_path: Path):
    """
    Very basic smoke test to see no exceptions arise from a simple conflict.
    """
    repo_path = str(conflict_repo_path)

    _ = collect(repo_path)
