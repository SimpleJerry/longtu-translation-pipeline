# CLAUDE.md

Constitution for every agent working in this repository. When guidance here conflicts with a request, surface the conflict before proceeding — never resolve it silently. This file is the single normative instruction source.

## Mission

The end goal of this project is a **deployable zh-CN → ko translation model that serves inference**, not a one-off experiment.

Optimize every change for that trajectory: preserve translation correctness and terminology fidelity, keep training and evaluation reproducible, reduce technical debt, and keep the system understandable enough to evolve toward deployment.

A contribution is acceptable only if it preserves system stability while doing at least one of: improving understanding, improving maintainability, or delivering product value.

For current scope, see the product documentation under [`docs/product`](docs/product/README.md).

## Source of Truth

When information conflicts, defer in this order:

1. ADRs under [`docs/decisions/adr`](docs/decisions/adr/README.md)
2. Architecture documents under [`docs/architecture`](docs/architecture/README.md)
3. Product and business documentation under [`docs/product`](docs/product/README.md)
4. Existing code
5. Assumptions

Never silently overwrite a documented decision. To change one, propose an ADR. Planning and process records are an archive, not a source of truth — read them for context, never treat their backlog items as current direction.

## Invariants

Some decisions are **invariants**: they may not be changed without a new ADR that supersedes the one that established them. The authoritative catalogue is the ADR index. Treat anything recorded there as binding until explicitly superseded.

## Architecture Principles

Hold these unless an ADR explicitly changes them:

- **Reproducibility first.** Do not introduce nondeterminism into the data-split, training-seed, or evaluation path. Any run that produces a reported number must be reconstructable from recorded settings.
- **Thin interfaces, pure core.** Keep reusable transformation logic in importable modules; keep entry-point scripts thin. Core logic must not depend on an entry-point script.
- **Configuration over hard-coding.** Paths, language codes, and hyperparameters live in configuration, not in source.
- **Separate data, model, and evaluation concerns.** Evaluation must not observe the held-out test set except for a single final report.
- **Version-controllable artifacts.** Prefer text-based, reviewable artifacts; keep heavy, binary, or regenerable outputs out of version control.
- Prefer maintainability and auditability over cleverness.

## Working Modes

Declare the active mode at the start of a session; do not switch modes silently.

- **Discovery** — understand the system. Analyze, document, ask questions. Do not refactor, change behavior, or make architectural decisions.
- **Design** — evaluate options. Compare alternatives, identify tradeoffs, produce ADR proposals. Do not implement.
- **Implementation** — execute approved work. Implement one specific task, keep changes small, update tests and docs. Do not perform unrelated refactors or introduce architecture changes without an approved ADR.

## ADR Rules

Significant decisions require an ADR: changes to data schema; the split / seed / ratio contract; terminology-marker conventions; training or evaluation methodology; model-artifact and reproducibility policy; data-cleaning or LLM-cleanup policy; and the inference / serving contract. Implementation details — a new test, a value tweak inside an existing config profile, or a behavior-preserving refactor — do not.

ADR title format: English ID plus a descriptive title — e.g. `ADR-0005: Gradual Engineering Refactor Approach`. New ADRs continue the existing numbering.

## Documentation Rules

- Architecture changes must update the architecture docs and the relevant ADR status.
- Behavior changes (entry-point surface, data schema, cleanup rules, evaluation metrics, serving contract) must update the product docs, the affected ADR, and user-facing descriptions.
- The READMEs are the public face and ship tri-lingual (ko / en / zh); keep them consistent when a user-facing fact changes. Do not duplicate volatile numbers (corpus counts, fingerprints) into them — reference where the data actually lives.

## Testing Rules

When modifying code:

1. Identify existing tests.
2. Preserve existing behavior unless a change is specified.
3. Add characterization tests for legacy behavior when needed.
4. Add or update automated tests.
5. Verify affected workflows.

Run the narrowest checks that prove the change is safe, plus the project test suite. For data-pipeline changes, use a dry-run or fixture that needs no private data or large model downloads. Never remove a test without stated justification.

## Session Rules

Each session must have a single objective, reference the relevant ADRs, define its success criteria, be reviewable on its own, and leave the repository in a working state.

- One logical change per commit; separate mechanical moves from behavior changes; do not stage unrelated changes.
- Record the actual validation commands and outcomes; mention any skipped checks and why.
- After a successful dependency install, update the requirements files in the same change; record only what installed successfully.
- Do not push to a shared remote without explicit user confirmation.

## Communication Style

Separate facts, inferences, assumptions, and recommendations. Raise an **Open Questions** section whenever uncertainty remains. Never invent missing information.

## Language Policy

- **Conversation** follows the user — currently Chinese (中文优先,英文次要).
- **Knowledge base** (`docs/`) single source of truth is Chinese (mixed zh/en); non-Chinese versions are generated on demand and not committed.
- **Skeleton is never translated:** code identifiers, file paths and commands, IDs (`ADR-XXXX`), and established technical names stay in English / their original form. In zh/en mixed prose, use English for terms that Chinese ML/software practitioners habitually write in English (e.g. Agent, Notebook, pipeline, backlog, dry-run, embedding, scaffolding, gate); translate only terms with settled Chinese field equivalents (e.g. 语料 corpus, 微调 fine-tuning, 推理 inference, 拆分 split, 检查点 checkpoint).
- **READMEs are a deliberate exception** — they ship tri-lingual (ko / en / zh) as the public face.
- **Commit messages and code comments** are English.
- The model's target language `ko` and the bilingual `zh` / `ko` corpora are domain data, not a UI i18n track; this repository has no shippable UI-locale assets.
