# Conflict 5‑Tuple Model

`Conflict5Tuple` captures the canonical five versions involved in a merge conflict:

| Symbol | Field | Description |
| ------ | ----- | ----------- |
| A | `ours_content` | Our side's version |
| B | `theirs_content` | Their side's version |
| O | `base_content` | Base (possibly virtual) version |
| M | `conflict_content` | File content with Git conflict markers |
| R | `resolved_content` | Post-resolution version (may be absent) |

## Usage

```python
from conflict_collection.schema.five_tuple import Conflict5Tuple
from conflict_parser import MergeMetadata

record = Conflict5Tuple(
    ours_content="...",
    theirs_content="...",
    base_content="...",
    conflict_content="<<<<<<< HEAD\n...=======\n...>>>>>>> branch\n",
    resolved_content=None,
    merge_config=MergeMetadata(conflict_style="merge"),
)
```

The model is a Pydantic `BaseModel` for validation and serialisation.
