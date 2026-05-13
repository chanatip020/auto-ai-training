"""Deterministic train/val/test split.

Reproducibility: the RNG is seeded by the dataset_id (UUID) so the same
dataset always produces the same v1 split, regardless of who runs the
conversion or when.
"""
from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Iterable, Sequence, TypeVar


DEFAULT_RATIOS: dict[str, float] = {"train": 0.70, "val": 0.20, "test": 0.10}
T = TypeVar("T")


@dataclass
class Split:
    train: list
    val: list
    test: list


def validate_ratios(ratios: dict[str, float]) -> None:
    keys = set(ratios)
    if keys != {"train", "val", "test"}:
        raise ValueError(
            "Split must have exactly the keys 'train', 'val', 'test'; got " + str(sorted(keys))
        )
    if any(v < 0 for v in ratios.values()):
        raise ValueError("Split ratios cannot be negative")
    total = sum(ratios.values())
    if not (0.999 <= total <= 1.001):
        raise ValueError(f"Split ratios must sum to 1.0 (got {total:.4f})")


def _seed_from_uuid(u: uuid.UUID) -> int:
    return int(u) & 0x7FFFFFFF


def split_items(
    items: Sequence[T],
    *,
    ratios: dict[str, float] | None = None,
    seed: uuid.UUID | int,
    sort_key=lambda x: str(x),
) -> Split:
    """Deterministic split.

    Steps:
      1. sort `items` for stability (any order in -> same order before shuffle)
      2. shuffle with a fixed seed
      3. cut at floor(n * train) and floor(n * (train+val)) boundaries
    """
    ratios = ratios or DEFAULT_RATIOS
    validate_ratios(ratios)

    ordered = sorted(items, key=sort_key)
    n = len(ordered)
    if n == 0:
        return Split([], [], [])

    seed_int = _seed_from_uuid(seed) if isinstance(seed, uuid.UUID) else int(seed)
    rng = random.Random(seed_int)
    shuffled = ordered.copy()
    rng.shuffle(shuffled)

    train_n = int(n * ratios["train"])
    val_n = int(n * ratios["val"])
    # Anything left over goes to test to avoid floor() dropping samples.
    return Split(
        train=shuffled[:train_n],
        val=shuffled[train_n:train_n + val_n],
        test=shuffled[train_n + val_n:],
    )


def pair_images_with_labels(
    images: Iterable, label_lookup: dict[str, "object"]
) -> list[tuple[object, object | None]]:
    """Match each image to its label by stem (filename without extension).

    Returns list of (image_path, label_path_or_None).
    """
    result: list[tuple[object, object | None]] = []
    for img in images:
        stem = getattr(img, "stem", str(img).rsplit(".", 1)[0].split("/")[-1])
        result.append((img, label_lookup.get(stem)))
    return result
