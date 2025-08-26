# Typed Conflict Cases

Immutable dataclasses (frozen, slots) describing concrete conflict manifestations. All variants share the conceptual fields: paths, contents per side, the conflict body, and resolution metadata (path/content may be deleted).

Variants:

- `ModifyModifyConflictCase`
- `ModifyDeleteConflictCase`
- `DeleteModifyConflictCase`
- `DeleteDeleteConflictCase`
- `AddedByUsConflictCase`
- `AddedByThemConflictCase`
- `AddAddConflictCase`

Each exposes a `conflict_type` literal string suitable for grouping.

See full auto-generated reference: [typed cases](../api/typed_five_tuple_models.md).
