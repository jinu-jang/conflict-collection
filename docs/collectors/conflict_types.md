# Conflict Type Collection

The conflict type collector reads the unmerged index (`git ls-files -u`) and groups related index entries into cohesive conflict "families". Each family is normalised into one of the typed dataclasses defined in `typed_five_tuple`.

## Usage

```python
from conflict_collection.collectors.conflict_type import collect

cases = collect(repo_path=".", resolution_sha="<resolved-commit-sha>")
for c in cases:
    print(c.conflict_type, c.conflict_path)
```

## Returned Types

- `ModifyModifyConflictCase`
- `ModifyDeleteConflictCase`
- `DeleteModifyConflictCase`
- `DeleteDeleteConflictCase`
- `AddedByUsConflictCase`
- `AddedByThemConflictCase`
- `AddAddConflictCase`

All cases share the semantic fields: paths, per-side contents, conflict body (with markers when applicable), and resolution information.

## Edge Cases & Notes

- Auto-resolved files (Git considers them conflicted internally but markers removed) are skipped.
- Delete / add sequencing in rename-rename scenarios surfaces as multiple cases (`delete_delete` → `added_by_us` → `added_by_them`).
- `resolution_sha` should be the commit after you have resolved conflicts (or any commit providing the final file blobs for comparison). If the resolution isn't committed yet, you can create a WIP commit or adapt the reader to inspect the worktree directly.

## API Reference

See the auto-generated API docs: [collector function](../api/collect_conflict_types.md).
