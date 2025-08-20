import contextlib
import os
from pathlib import Path

import pytest
from git import GitCommandError, Repo

DEFAULT_BUNDLE = Path(__file__).parent / "_fixtures" / "merge-conflict-demo.bundle"
"""Path to the default bundle to unpack into a merge conflict."""


@contextlib.contextmanager
def _patched_env(**overrides):
    old = {k: os.environ.get(k) for k in overrides}
    try:
        os.environ.update({k: str(v) for k, v in overrides.items() if v is not None})
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _find_bundle(start: Path) -> Path:
    """
    Check for where the bundle file is in following priority:
    1. Env var $TEST_GIT_BUNDLE
    2. Default bundle included under ./_fixtures/
    3. Up the repo looking for ./tests/fixtures/
    """
    # 1) explicit override
    env = os.getenv("TEST_GIT_BUNDLE")
    if env and Path(env).exists():
        return Path(env)

    # 2) common locations: tests/_fixtures/...
    if DEFAULT_BUNDLE.exists():
        return DEFAULT_BUNDLE

    # 3) walk up to repo root looking for tests/fixtures
    for p in (start, *start.parents):
        c = p / "tests" / "fixtures" / "merge-conflict-demo.bundle"
        if c.exists():
            return c

    raise FileNotFoundError(
        "merge-conflict-demo.bundle not found. "
        "Place it at tests/fixtures/ or set TEST_GIT_BUNDLE=/path/to/bundle"
    )


@pytest.fixture
def conflict_repo_path(tmp_path: Path):
    """
    Clone the demo bundle into a temp dir and perform `git merge theirs` on `main`,
    leaving an in-progress merge conflict. Returns the repo path (Path).
    """
    bundle = _find_bundle(Path(__file__).parent)
    repo_dir = tmp_path / "repo"
    null = "nul" if os.name == "nt" else "/dev/null"

    # Keep Git isolated from user/system config
    with _patched_env(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=null,
        GIT_TERMINAL_PROMPT="0",
    ):
        repo = Repo.clone_from(str(bundle), repo_dir)
        # Normalize line endings and avoid platform surprises
        repo.git.config("core.autocrlf", "false")
        repo.git.checkout("main")

        # Intentionally cause a conflict:
        # 1) Try to merge "theirs"
        # 2) If that fails without producing a conflict, try "remotes/origin/theirs"
        try:
            repo.git.merge("theirs")
            # If we got here with no exception, the merge completed cleanly (unexpected for this demo)
            # We'll let the post-merge assertions below fail if no conflict exists.
        except GitCommandError as e:
            text = (e.stdout or "") + (e.stderr or "")
            if "CONFLICT" not in text:
                # Fallback: remote-tracking ref
                try:
                    repo.git.merge("remotes/origin/theirs")
                except GitCommandError as e2:
                    text2 = (e2.stdout or "") + (e2.stderr or "")

                    # If still no conflict, surface the second failure for context
                    if "CONFLICT" not in text2:
                        raise e2

        # Sanity: conflict present for conflict.txt; ok.txt exists
        unmerged = set(Repo(repo_dir).index.unmerged_blobs().keys())
        assert "conflict.txt" in unmerged, "Expected a conflict in conflict.txt"
        assert (repo_dir / "ok.txt").exists(), "ok.txt should be present"

        yield repo_dir  # <- pass this Path to your library
