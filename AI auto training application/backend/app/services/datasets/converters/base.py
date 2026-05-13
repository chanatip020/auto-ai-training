"""Base converter contract.

A converter takes:
  - input_dir: extracted raw dataset (whatever the user uploaded)
  - output_dir: where to write the normalized layout
  - ratios: {'train', 'val', 'test'} ratios summing to 1.0
  - classes_override: optional explicit class list (otherwise auto-detect)
  - seed: UUID used to make the split deterministic

…and returns a ConversionResult with summary stats the caller persists.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConversionResult:
    format: str
    classes: list[str]
    num_images: int
    num_labels: int
    counts: dict[str, int]                 # per-split image counts
    notes: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


class BaseConverter(ABC):
    """All converters expose the same .convert() signature."""

    #: format string for the dataset_versions.format column (e.g. 'yolo-det')
    format_id: str = ""

    @abstractmethod
    def convert(
        self,
        *,
        input_dir: Path,
        output_dir: Path,
        ratios: dict[str, float],
        classes_override: list[str] | None,
        seed: uuid.UUID,
    ) -> ConversionResult: ...
