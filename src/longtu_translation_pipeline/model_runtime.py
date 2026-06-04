"""Tokenizer / device / checkpoint runtime utilities.

Shared across training and inference stacks.  Top-level imports are stdlib-only;
``torch`` is imported lazily inside each function that needs it so that
dry-run / serving / CI-CPU import paths stay lightweight (ADR-0014, ADR-0042).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def configure_tokenizer_language_codes(tokenizer: Any, src_code: str, tgt_code: str) -> list[str]:
    """Set tokenizer src_lang / tgt_lang and return a list of applied assignments."""
    assignments: list[str] = []
    for attribute, value in (
        ("src_lang", src_code),
        ("tgt_lang", tgt_code),
    ):
        try:
            setattr(tokenizer, attribute, value)
        except Exception:
            continue
        assignments.append(f"{attribute}={value}")
    return assignments


def add_marker_special_tokens(tokenizer: Any) -> int:
    """Add ``<start>`` / ``<end>`` special tokens; return the count added."""
    marker_tokens = {"additional_special_tokens": ["<start>", "<end>"]}
    try:
        return tokenizer.add_special_tokens(
            marker_tokens,
            replace_additional_special_tokens=False,
        )
    except TypeError:
        return tokenizer.add_special_tokens(
            marker_tokens,
            replace_extra_special_tokens=False,
        )


def list_checkpoint_paths(output_dir: str | Path) -> list[Path]:
    """Return all ``checkpoint-N`` subdirectories sorted by step number."""
    path = Path(output_dir)
    if not path.exists():
        return []

    checkpoints: list[tuple[int, Path]] = []
    for child in path.iterdir():
        if not child.is_dir() or not child.name.startswith("checkpoint-"):
            continue
        step_text = child.name[len("checkpoint-"):]
        try:
            step = int(step_text)
        except ValueError:
            continue
        checkpoints.append((step, child))
    return [checkpoint for _, checkpoint in sorted(checkpoints)]


def find_latest_checkpoint(output_dir: str | Path) -> Path | None:
    """Return the highest-step ``checkpoint-N`` directory, or ``None`` if absent."""
    checkpoints = list_checkpoint_paths(output_dir)
    if not checkpoints:
        return None
    return checkpoints[-1]


def resolve_training_device(device: str) -> str:
    """Resolve ``"auto"`` to ``"cuda"`` or ``"cpu"``; validate explicit choices."""
    if device not in {"auto", "cuda", "cpu"}:
        raise ValueError("device must be one of: auto, cuda, cpu")

    import torch

    cuda_available = torch.cuda.is_available()
    if device == "auto":
        return "cuda" if cuda_available else "cpu"
    if device == "cuda" and not cuda_available:
        raise RuntimeError("CUDA was requested but torch.cuda.is_available() is False")
    return device


def cuda_device_name(device: str) -> str:
    """Return the CUDA device name, or ``"none"`` when not on CUDA."""
    if device != "cuda":
        return "none"

    import torch

    return torch.cuda.get_device_name(0)


def cuda_memory_summary(device: str) -> str:
    """Return a compact memory summary string, or ``"none"`` when not on CUDA."""
    if device != "cuda":
        return "none"

    import torch

    allocated = torch.cuda.memory_allocated(0) / (1024**3)
    reserved = torch.cuda.memory_reserved(0) / (1024**3)
    return f"allocated_gb={allocated:.2f};reserved_gb={reserved:.2f}"
