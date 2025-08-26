# Contributing

Thanks for considering a contribution! Please help maintain a high signal-to-noise ratio.

## Workflow

1. Fork & create a feature branch
2. `pip install -e .[dev,docs]`
3. Add / adjust tests (keep coverage high)
4. Format & lint: `black . && isort .`
5. Run tests: `pytest -q`
6. (Optional) Build docs locally: `mkdocs serve`
7. Submit PR with concise description & motivation

## Commit Messages

Use clear, conventional style prefixes when possible (`feat:`, `fix:`, `docs:`, `refactor:`). Keep the first line ≤ 72 chars.

## Code Style

- Python ≥ 3.10 (structural typing, dataclasses, pattern matching OK)
- Prefer explicit over implicit; keep internal helpers underscored
- Document tricky algorithms with short rationale comments

## Testing

Target meaningful edge cases: empty conflicts, unusual delete/add combinations, large blame tables, insertion-heavy diffs.

## Documentation

Public APIs should have docstrings. If you add a module, add it to `mkdocs.yml` nav or an existing section.

## Release Process

Maintainers will bump version in `pyproject.toml`, tag, and publish to PyPI. Changelog entries should accompany user-visible changes.

## Code of Conduct

Be respectful and assume positive intent.
