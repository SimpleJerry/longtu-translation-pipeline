# AI/Codex Working Rules

This file defines how AI/Codex agents should work in this repository. It is not the long-term refactor task pool.

## Refactor Task Source

- Use `docs/refactor/backlog.md` as the single source of truth for refactor TODOs.
- Use `docs/refactor/decisions.md` for confirmed architecture decisions and tradeoffs that should not be re-litigated without new context.
- Keep README files focused on project introduction, setup, basic usage, and navigation links.

## Choosing Work

- Before starting a refactor, read the backlog and pick one task by ID.
- Prefer the next high-impact TODO item that has clear acceptance criteria and can be completed independently.
- Do not mix unrelated refactors in the same change. If a new issue is discovered, add or update a backlog item instead of folding it into the current task.
- If a task is ambiguous, mark it `NEEDS_TRIAGE` or `BLOCKED` in the backlog with the missing decision.

## Compatibility

- Preserve public APIs, command names, file formats, and documented workflows unless the selected task explicitly calls for a breaking change.
- When a breaking change is required, update the backlog item, README entry points, and any migration notes in the same change.
- Keep notebooks usable as experiment records unless the selected task explicitly migrates or removes them.

## Completion Rules

- Update the selected backlog item status before finishing:
  - `TODO`: not started.
  - `DOING`: actively being worked on.
  - `BLOCKED`: cannot proceed without a decision or dependency.
  - `DONE`: implemented and verified.
- Record the actual validation commands and outcomes in the backlog item.
- Mention any skipped checks and why.
- Leave unrelated local changes untouched, especially IDE files and generated data.

## Documentation Consistency

- Keep implementation, README entry points, backlog notes, decision records, and script comments consistent.
- When changing a data schema, CLI behavior, pipeline rule, or cleanup criterion, update the relevant documentation in the same change.
- Do not leave docs implying an old behavior after the code has changed.

## Required Checks

Run the narrowest checks that prove the selected task is safe. For documentation-only changes, run:

```powershell
git -c safe.directory=D:/longtu-translation-pipeline status --short
git -c safe.directory=D:/longtu-translation-pipeline diff --check
rg -n -i "TODO|FIXME|NEEDS_TRIAGE|backlog|decisions" AGENTS.md docs/refactor
```

For Python code changes, also run targeted unit tests or import checks. The full test suite uses Python's stdlib unittest:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests
```

Individual tests can be run with `python -m unittest tests.<module>`.

For data pipeline changes, include a small fixture or dry-run command that does not require private data or large model downloads.

## Code Style

- Follow the existing Python style until a formatter is introduced.
- Keep pure transformation logic in importable modules and keep CLI scripts thin.
- Prefer explicit config files over hard-coded local paths.
- Use stable, text-based artifacts for version control whenever practical.

## Dependency Governance

- After automatically installing any pip package, update `requirements.txt` in the same change.
- Record dependencies that were actually installed successfully.
- Do not add packages from failed temporary install attempts to `requirements.txt`.

## Commit Granularity

- Keep one backlog item per commit when possible.
- Separate mechanical moves from behavior changes.
- Do not stage unrelated user or IDE changes.

## Acceptance Standard

A task is complete only when:

- Its backlog item status and validation notes are updated.
- Relevant README or docs links are current.
- Required checks were run or explicitly documented as skipped.
- The resulting change can be reviewed without needing unrelated context.
