"""Pytest session bootstrap shared by all test files.

Import torch eagerly, first thing, before pytest collects any test module
that pulls in the heavy NLP native libraries (stanza, kiwipiepy, transformers,
accelerate).

Why: the product code imports torch lazily inside functions (see
``longtu_translation_pipeline.training``) to keep non-training entry points
light. On Linux CI that first ``import torch`` then happens *mid-test*, after a
pytest-xdist worker has already loaded the other native libraries into its
process. Initializing torch's C extension from that polluted state fails: the
CUDA build segfaults (crashing the worker and hanging the run), and the CPU
build raises ``RuntimeError: THPDtypeType.tp_dict == nullptr`` during
``torch/__init__.py``.

Importing torch here -- before collection, in a pristine interpreter state that
every xdist worker reaches at startup -- initializes those C types once. Every
later ``import torch`` is then a cached no-op and cannot re-trigger the broken
initialization.
"""

try:
    import torch  # noqa: F401
except ImportError:
    # torch is an optional dependency for the non-training test files; if it is
    # not installed, let those tests run and let the training tests fail with a
    # clear ImportError rather than blocking collection here.
    pass
