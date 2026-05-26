# Task Briefs

Self-contained briefings for the parallel follow-up tasks defined in
[../follow-up-tasks.md](../follow-up-tasks.md).

Each brief is designed so a fresh conversation can pick up the task cold
without needing to re-read the entire repository. A brief points at the
backlog item it implements, the audit finding it addresses (if any), the
locked decisions it must respect, and the files it is allowed to touch.

## Naming

`T-{track}{n}.md` where `{track}` is `A` (critical path), `B`
(engineering hardening), `C` (test backfill), `D` (API & notebook),
`E` (doc drift), or `F` (research extension).

| Track | What it is | Parallel within track? |
|-------|------------|------------------------|
| A | LLM segments full apply → 10k re-train → validation → final test | **No** (each step mutates segments.csv or depends on the previous checkpoint) |
| B | Engineering hardening from the 2026-05-26 audit P1 items | Yes |
| C | Test coverage backfill (RF-016 sub-phases) | Yes |
| D | Public API surface and notebook archival hygiene | Yes |
| E | Documentation drift fixes | Yes |
| F | Research extensions (extra metrics, larger base models, augmentation, inference sweeps) | Mostly yes; F3/F4/F5 share GPU time |

## Workflow for a new conversation

1. Read the brief end-to-end.
2. Confirm prerequisites (credentials, prior tasks). If a prerequisite is
   not met, stop and report — do not push past the gate.
3. Read the shared context links and the listed "files to read first".
4. Make the change in one commit per RF item (per `AGENTS.md`).
5. Update the corresponding backlog item from `TODO` / `DOING` to
   `DONE` (or `BLOCKED` with explanation).
6. Run the verification commands listed in the brief.
7. Do not push to `origin/main` unless the user explicitly authorizes it.

## Collision avoidance

`data/segments.csv`, `data/glossary.csv`, `requirements*.txt`,
`src/longtu_translation_pipeline/__init__.py`, and the `notebooks/`
directory tree are mutually exclusive write surfaces. Briefs annotate
which surfaces they touch under "Modification surface" and which to
"Don't touch". Two parallel conversations should never both list the
same file under "Modification surface".

`docs/refactor/backlog.md` is also shared, but each task only edits its
own RF section. If a downstream conversation hits a merge conflict with
an upstream RF section, the resolution is mechanical: take the upstream
version and re-apply your own RF section on top.
