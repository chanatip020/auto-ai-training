"""YOLO classification converter.

Different on-disk layout from detection/segmentation. Ultralytics expects
class-named subfolders under each split:

    {output}/train/<class_name>/<img>
    {output}/val/<class_name>/<img>
    {output}/test/<class_name>/<img>

Input layout (one of):
  (a) class folders directly under the input dir:
        input/<class_name>/<img>
  (b) train/val[/test] already split with class subfolders:
        input/train/<class_name>/<img>
"""
from __future__ import annotations

import shutil
import uuid
from collections import defaultdict
from pathlib import Path

from app.core.errors import AppError
from app.services.datasets.converters.base import BaseConverter, ConversionResult
from app.services.datasets.detect import IMAGE_EXTS
from app.services.datasets.split import split_items


def _scan_class_folders(root: Path) -> dict[str, list[Path]]:
    """Map class_name -> list of image paths under that class.

    Handles two input layouts: class folders directly under root, or
    already-split (train/<class>/<img>) layouts.
    """
    by_class: dict[str, list[Path]] = defaultdict(list)

    # Pattern A: <root>/<class>/<image>
    direct_classes = [d for d in root.iterdir() if d.is_dir()]
    saw_split_root = any(d.name.lower() in ("train", "val", "valid", "test") for d in direct_classes)

    if saw_split_root:
        # Pattern B: collapse splits back into class -> images
        for split_dir in direct_classes:
            if not split_dir.is_dir() or split_dir.name.lower() not in ("train", "val", "valid", "test"):
                continue
            for class_dir in split_dir.iterdir():
                if not class_dir.is_dir():
                    continue
                cls = class_dir.name
                for f in class_dir.rglob("*"):
                    if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                        by_class[cls].append(f)
    else:
        for class_dir in direct_classes:
            cls = class_dir.name
            for f in class_dir.rglob("*"):
                if f.is_file() and f.suffix.lower() in IMAGE_EXTS:
                    by_class[cls].append(f)

    return by_class


class YoloClassificationConverter(BaseConverter):
    format_id = "yolo-cls"

    def convert(
        self,
        *,
        input_dir: Path,
        output_dir: Path,
        ratios: dict[str, float],
        classes_override: list[str] | None,
        seed: uuid.UUID,
    ) -> ConversionResult:
        if not input_dir.exists():
            raise AppError("CONVERT_NO_INPUT",
                           f"Input directory missing: {input_dir}", 400)

        by_class = _scan_class_folders(input_dir)
        if not by_class:
            raise AppError(
                "CONVERT_NO_CLASSES",
                "Classification expects class-named subfolders. None were found.",
                status_code=400,
            )

        if classes_override:
            # Restrict to user-provided class list if given (preserves order)
            by_class = {c: by_class[c] for c in classes_override if c in by_class}
            if not by_class:
                raise AppError(
                    "CONVERT_NO_CLASS_MATCH",
                    "None of the requested classes were found in the dataset.",
                    400,
                )

        classes = list(by_class.keys())

        # Prepare output tree
        if output_dir.exists():
            shutil.rmtree(output_dir)
        for split_name in ("train", "val", "test"):
            for cls in classes:
                (output_dir / split_name / cls).mkdir(parents=True, exist_ok=True)

        counts: dict[str, int] = {"train": 0, "val": 0, "test": 0}
        total_images = 0
        per_class_counts: dict[str, dict[str, int]] = {}

        for cls in classes:
            files = by_class[cls]
            total_images += len(files)
            sp = split_items(files, ratios=ratios, seed=seed,
                             sort_key=lambda p: p.name)
            per_class_counts[cls] = {
                "train": len(sp.train), "val": len(sp.val), "test": len(sp.test),
            }
            for split_name in ("train", "val", "test"):
                items: list[Path] = getattr(sp, split_name)
                counts[split_name] += len(items)
                for src in items:
                    dst = output_dir / split_name / cls / src.name
                    shutil.copyfile(src, dst)

        return ConversionResult(
            format=self.format_id,
            classes=classes,
            num_images=total_images,
            num_labels=total_images,  # in classification, every image is implicitly labeled by folder
            counts=counts,
            notes=[],
            extra={"ratios": ratios, "per_class_counts": per_class_counts},
        )
