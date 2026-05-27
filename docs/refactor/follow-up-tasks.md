# Follow-Up Tasks (Parallel Track Map)

This file is the **dispatch index** for follow-up work after the
2026-05-26 audit. Each task below is designed to be sent to a fresh
conversation as an independent unit. Self-contained briefings live in
[task-briefs/](task-briefs/).

For the audit findings these tasks resolve, see
[audit-2026-05-26.md](audit-2026-05-26.md). For the canonical RF log,
see [backlog.md](backlog.md). Do not duplicate those documents here —
this file is a navigational layer.

---

## Why a separate index

Most of the work post-2026-05-26 falls into independent buckets:

- One mutually exclusive critical-path chain (data → train → eval).
- Many independent engineering / test / doc tasks that don't touch
  shared mutable state.
- A handful of research extensions that depend on the critical-path
  result but can otherwise run in parallel.

The user is dispatching these across multiple conversations. This
index lists every task, its dependencies, its parallelism class, and
the brief that gets it started.

---

## Dependency DAG

```text
Track A  (sequential, critical path — first 4 done as historical baseline)
  T-A1 (RF-015 full LLM segments apply)               [DONE]
      └─> T-A2 (RF-006-P11 re-train 10k)              [DONE]
              └─> T-A3 (RF-006-P12 validation report) [DONE]
                      └─> T-A4 (RF-007-P3 final held-out test report) [DONE — historical baseline]
                              └─> T-A5 (RF-006-P13 early-stopping training, composite metric)  [PENDING]
                                      └─> T-A6 (RF-007-P4 new held-out test on best checkpoint) [PENDING]

Track B  (parallel, engineering hardening — audit P1)
  T-B1 (RF-017 extract llm_common.py)       # recommended before T-A1
  T-B2 (RF-018 requirements torch consolidation)
  T-B3 (RF-019 default.json annotation)

Track C  (parallel, test backfill — RF-016 sub-phases)
  T-C1 (RF-016-P1 cleanup_common.py tests)
  T-C2 (RF-016-P2 segments_cleaning_pipeline.py tests)
  T-C3 (RF-016-P3 glossary_semantic_pipeline.py tests)

Track D  (parallel, API & notebook hygiene)
  T-D1 (RF-020 __init__.py public surface)
  T-D2 (RF-021 archive deprecated notebooks)

Track E  (parallel, doc drift)
  T-E1 (RF-022 AGENTS.md unittest + RF-003 obsolete)
  T-E2 (RF-023 README tri-language sync — optional large)

Track F  (parallel, research extensions; some depend on Track A)
  T-F1 (RF-024 chrF metric — backfill on existing reports OK)
  T-F2 (RF-025 COMET metric — optional, opt-in)
  T-F3 (RF-026 NLLB-1.3B / 3.3B base experiment)
  T-F4 (RF-027 back-translation augmentation)
  T-F5 (RF-028 inference parameter sweep)
```

---

## Suggested dispatch batches

### Batch 1 — fully parallel, no shared state collisions

Dispatchable immediately. Each touches a disjoint set of files.

| Task | Brief | Touches | Approx. cost |
|------|-------|---------|--------------|
| T-B1 | [task-briefs/T-B1.md](task-briefs/T-B1.md) | `scripts/llm_common.py` (new), 2 LLM scripts, tests | Small |
| T-B2 | [task-briefs/T-B2.md](task-briefs/T-B2.md) | `requirements*.txt`, README install paragraphs | XS |
| T-B3 | [task-briefs/T-B3.md](task-briefs/T-B3.md) | `configs/training/default.json`, README | XS |
| T-C1 | [task-briefs/T-C1.md](task-briefs/T-C1.md) | `tests/test_cleanup_common.py` (new) | Small |
| T-D1 | [task-briefs/T-D1.md](task-briefs/T-D1.md) | `src/longtu_translation_pipeline/__init__.py` | XS |
| T-D2 | [task-briefs/T-D2.md](task-briefs/T-D2.md) | `notebooks/`, `docs/notebooks/inventory.md`, READMEs | Small |
| T-E1 | [task-briefs/T-E1.md](task-briefs/T-E1.md) | `AGENTS.md`, `backlog.md` RF-003 section | XS |

### Batch 2 — runs alongside Track A

| Task | Brief | Touches | Notes |
|------|-------|---------|-------|
| T-A1 | [task-briefs/T-A1.md](task-briefs/T-A1.md) | `data/segments.csv` | Spends API tokens; needs explicit user authorization |
| T-C2 | [task-briefs/T-C2.md](task-briefs/T-C2.md) | `tests/test_segments_cleaning_pipeline.py` | Medium |
| T-C3 | [task-briefs/T-C3.md](task-briefs/T-C3.md) | `tests/test_glossary_semantic_pipeline.py` (new) | Medium-large |
| T-E2 | [task-briefs/T-E2.md](task-briefs/T-E2.md) | three READMEs (or new sync script) | Large, optional |

### Batch 3 — after Track A starts producing artifacts

| Task | Brief | Depends on |
|------|-------|------------|
| T-A2 | [task-briefs/T-A2.md](task-briefs/T-A2.md) | T-A1 |
| T-A3 | [task-briefs/T-A3.md](task-briefs/T-A3.md) | T-A2 |
| T-A4 | [task-briefs/T-A4.md](task-briefs/T-A4.md) | T-A3 |
| T-F1 | [task-briefs/T-F1.md](task-briefs/T-F1.md) | none (can backfill on historical) |

### Batch 4 — after T-A4 (final test report exists)

| Task | Brief | Notes |
|------|-------|-------|
| T-F2 | [task-briefs/T-F2.md](task-briefs/T-F2.md) | Optional; opt-in COMET |
| T-F3 | [task-briefs/T-F3.md](task-briefs/T-F3.md) | GPU-bound; larger base model comparison |
| T-F4 | [task-briefs/T-F4.md](task-briefs/T-F4.md) | Synthetic data; isolation contract critical |
| T-F5 | [task-briefs/T-F5.md](task-briefs/T-F5.md) | Cheapest research extension; no training |

---

## Collision avoidance summary

Two parallel conversations **must not** both list the same file under
"Modification surface" in their briefs. The mutually exclusive write
surfaces are:

- `data/segments.csv`, `data/glossary.csv` — only T-A1
- `fine-tuned-models/.../runs/run-*` — one Track A task at a time
- `requirements.txt`, `requirements-training.txt` — only T-B2 (and
  T-F2 if COMET is opt-in)
- `src/longtu_translation_pipeline/__init__.py` — only T-D1
- `notebooks/main/` ↔ `notebooks/archive/` — only T-D2
- `AGENTS.md` — only T-E1

`docs/refactor/backlog.md` is shared but each task only edits its own
RF section. Conflicts on backlog.md are mechanical to resolve (take
the upstream, re-apply your section).

---

## How to use this index

1. Pick an unblocked task (check the DAG and the "Blocked-by" line in
   the brief).
2. Open a new conversation. Say: "execute T-XX following the brief at
   `docs/refactor/task-briefs/T-XX.md`."
3. The conversation reads the brief, the shared context links, the
   relevant RF in backlog.md, and proceeds.
4. When done, the conversation updates the corresponding RF status in
   backlog.md to `DONE` (or `BLOCKED` with reason) in the same
   commit, and does not push without your explicit OK.

---

## Maintenance

- When a task starts, set its backlog RF to `DOING`.
- When a task finishes, set the RF to `DONE` and record the actual
  validation output (per AGENTS.md "Completion Rules").
- If a brief turns out to be wrong (e.g. the task is bigger than
  expected, or the audit assumption changed), update the brief or
  open a `BLOCKED` note rather than improvising mid-task.
- Add new tasks to this index by appending an entry above and writing
  a new brief; keep the RF id range consecutive.
