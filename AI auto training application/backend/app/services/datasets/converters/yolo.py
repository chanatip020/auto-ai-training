"""YOLO detection + segmentation converter.

Detection and segmentation share an identical *file organization* in YOLO
format — both have:

    images/{train,val,test}/<name>.<ext>
    labels/{train,val,test}/<name>.txt

The .txt file content differs (bbox vs polygons) but the converter is
purely about pairing images with labels and splitting, so a single class
handles both. The only difference is the ``format_id`` we tag on the
DatasetVersion.
"""
from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from app.core.errors import AppError
from app.services.datasets.converters.base import BaseConverter, ConversionResult
from app.services.datasets.detect import IMAGE_EXTS, NON_LABEL_TXT
from app.services.datasets.split import split_items
from app.services.datasets.yaml_writer import write_data_yaml


def _index_files(root: Path) -> tuple[list[Path], dict[str, Path]]:
    """Scan the raw extraction. Returns (images, labels_by_stem)."""
    images: list[Path] = []
    labels: dict[str, Path] = {}
    for f in root.rglob("*"):
        if not f.is_file():
            continue
        ext = f.suffix.lower()
        name = f.name.lower()
        if ext in IMAGE_EXTS:
            images.append(f)
        elif ext == ".txt" and name not in NON_LABEL_TXT:
            # Use stem (filename without extension) as the join key.
            labels[f.stem] = f
    return images, labels


def _resolve_classes(root: Path, override: list[str] | None) -> list[str]:
    if override:
        return list(override)
    # Prefer classes.txt / names.txt at the root.
    for name in ("classes.txt", "names.txt"):
        p = root / name
        if p.exists():
            return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return []


class _YoloFileConverter(BaseConverter):
    """Shared implementation for detection + segmentation."""

    format_id = "yolo-det"  # overridden in subclass

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

        images, labels = _index_files(input_dir)
        if not images:
            raise AppError(
                "CONVERT_NO_IMAGES",
                "No images found in the raw dataset; nothing to convert.",
                status_code=400,
            )

        classes = _resolve_classes(input_dir, classes_override)
        if not classes:
            raise AppError(
                "CONVERT_NO_CLASSES",
                "Classes are not defined. Provide classes_override or include "
                "classes.txt in the upload.",
                status_code=400,
            )

        # Pair images with labels by stem; record orphans for the summary
        paired: list[tuple[Path, Path | None]] = []
        for img in images:
            paired.append((img, labels.get(img.stem)))

        # Split deterministically by image (label follows its image)
        split = split_items(paired, ratios=ratios, seed=seed,
                            sort_key=lambda pair: pair[0].name)

        # Prepare output tree
        if output_dir.exists():
            shutil.rmtree(output_dir)
        for sub in ("images/train", "images/val", "images/test",
                    "labels/train", "labels/val", "labels/test"):
            (output_dir / sub).mkdir(parents=True, exist_ok=True)

        counts: dict[str, int] = {}
        orphan_count = 0
        labels_written = 0
        for split_name in ("train", "val", "test"):
            pairs = getattr(split, split_name)
            counts[split_name] = len(pairs)
            for img, lbl in pairs:
                # Copy image with original extension
                dst_img = output_dir / "images" / split_name / img.name
                shutil.copyfile(img, dst_img)
                if lbl is not None:
                    dst_lbl = output_dir / "labels" / split_name / (img.stem + ".txt")
                    shutil.copyfile(lbl, dst_lbl)
                    labels_written += 1
                else:
                    orphan_count += 1

        write_data_yaml(output_dir=output_dir, classes=classes,
                        has_test=counts.get("test", 0) > 0)

        notes: list[str] = []
        if orphan_count:
            notes.append(f"{orphan_count} image(s) had no matching .txt label; "
                         "they were copied without labels.")

        return ConversionResult(
            format=self.format_id,
            classes=classes,
            num_images=len(images),
            num_labels=labels_written,
            counts=counts,
            notes=notes,
            extra={"ratios": ratios, "data_yaml": "data.yaml"},
        )


class YoloDetectionConverter(_YoloFileConverter):
    format_id = "yolo-det"


class YoloSegmentationConverter(_YoloFileConverter):
    format_id = "yolo-seg"
