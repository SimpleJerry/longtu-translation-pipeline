# Invariants

This is the authoritative catalogue of the project's invariants — the
contracts referenced by the **Invariants** section of the constitution
([CLAUDE.md](../../CLAUDE.md)). Each is established by an ADR and may not
be changed without a new ADR that supersedes it. Treat every entry as
binding until explicitly superseded.

| Invariant | Contract | ADR |
|-----------|----------|-----|
| **Data schema** | `data/segments.csv` = `segment_id,zh-CN,ko`; `data/glossary.csv` = `term_id,zh-CN,ko`. Only the final corpora and configs are committed; checkpoints, run artifacts, review CSVs, and model caches stay git-ignored. | [ADR-0004](../decisions/adr/ADR-0004-csv-in-git-raw-xlsx-outside-git-tracking.md), [ADR-0017](../decisions/adr/ADR-0017-generation-evaluation-reports-are-local-artifacts.md) |
| **Split contract** | Deterministic train/validation/test = 8:1:1, seed 42; formal runs write split artifacts and a manifest carrying `segments_sha256`. | [ADR-0020](../decisions/adr/ADR-0020-formal-training-runs-require-split-artifacts-and-manifests.md), [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) |
| **Held-out test** | The test split is evaluated once, after checkpoint selection on validation. Iterating on test numbers is leakage. | [ADR-0023](../decisions/adr/ADR-0023-formal-experiments-use-held-out-test-splits.md) |
| **Terminology markers** | Single `<start>...<end>` shape only; `<middle>` and `<code_id=N>` are deprecated. | [ADR-0010](../decisions/adr/ADR-0010-text-protection-uses-single-segment-term-markers.md) |
| **Strict glossary gate** | Glossary↔segment strict consistency must pass before formal training. | [ADR-0019](../decisions/adr/ADR-0019-full-training-requires-strict-glossary-consistency-check.md) |
| **LLM cleanup policy** | Cloud glossary cleanup is delete-only; segment cleanup may rewrite only the Korean target and only after local validation. | [ADR-0025](../decisions/adr/ADR-0025-cloud-llm-glossary-cleanup-is-delete-only.md), [ADR-0026](../decisions/adr/ADR-0026-cloud-llm-segment-cleanup-may-rewrite-korean-with-local-guards.md) |
| **Checkpoint selection** | Formal training uses early stopping on a composite metric; the published checkpoint is chosen by full-validation re-ranking, not the in-loop auto-best. | [ADR-0031](../decisions/adr/ADR-0031-formal-training-uses-early-stopping-on-composite-metric.md) |
| **Public compatibility** | Preserve documented commands, config formats, and CSV schemas unless an ADR explicitly authorizes a breaking change. | [ADR-0006](../decisions/adr/ADR-0006-preserve-public-compatibility-by-default.md) |

To change an invariant, propose a superseding ADR; do not edit this table
to relax a contract ahead of the decision.
