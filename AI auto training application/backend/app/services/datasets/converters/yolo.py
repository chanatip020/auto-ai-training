"""YOLO detection + segmentation converter.

Detection and segmentation share an identical *file organization* in YOLO
format -- both have:

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
    """Resolve the YOLO class list.

    Search order:
      1. caller-supplied override
      2. classes.txt / names.txt at the root (standard YOLO)
      3. obj.names at the root (CVAT YOLO 1.1 export)
      4. any of the above one level deep (CVAT sometimes nests in obj_train_data/)
    """
    if override:
        return list(override)

    candidates: list[Path] = []
    for name in ("classes.txt", "names.txt", "obj.names"):
        candidates.append(root / name)
    if root.exists():
        for sub in root.iterdir():
            if sub.is_dir():
                for name in ("classes.txt", "names.txt", "obj.names"):
                    candidates.append(sub / name)

    for p in candidates:
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
        treat_unlabeled_as_background: bool = False,
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
                "Classes are not defined. Include classes.txt / names.txt "
                "(standard YOLO) or obj.names (CVAT YOLO 1.1 export) in the "
                "upload, or pass classes_override when starting the conversion.",
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
        # Orphan images come in two flavours:
        #  - intentional background images (treat_unlabeled_as_background=True):
        #    we materialize an empty .txt sidecar so Ultralytics treats them
        #    as explicit zero-object frames. Recommender will skip the
        #    "missing labels" blocker for these.
        #  - accidentally unlabeled images (default):
        #    we copy the image without a .txt and surface the count to the
        #    recommender, which decides whether it's a warning or blocker.
        background_count = 0
        unlabeled_count = 0
        labels_written = 0
        for split_name in ("train", "val", "test"):
            pairs = getattr(split, split_name)
            counts[split_name] = len(pairs)
            for img, lbl in pairs:
                dst_img = output_dir / "images" / split_name / img.name
                shutil.copyfile(img, dst_img)
                if lbl is not None:
                    dst_lbl = output_dir / "labels" / split_name / (img.stem + ".txt")
                    shutil.copyfile(lbl, dst_lbl)
                    labels_written += 1
                elif treat_unlabeled_as_background:
                    # Write an empty .txt sidecar — the YOLO convention for
                    # "this image is an intentional background, zero objects."
                    dst_lbl = output_dir / "labels" / split_name / (img.stem + ".txt")
                    dst_lbl.write_text("")
                    background_count += 1
                else:
                    unlabeled_count += 1

        write_data_yaml(output_dir=output_dir, classes=classes,
                        has_test=counts.get("test", 0) > 0)

        notes: list[str] = []
        if background_count:
            notes.append(
                f"{background_count} image(s) had no .txt label; an empty "
                f"sidecar was written for each (treated as background)."
            )
        if unlabeled_count:
            notes.append(
                f"{unlabeled_count} image(s) had no matching .txt label; "
                "they were copied without labels."
            )

        return ConversionResult(
            format=self.format_id,
            classes=classes,
            num_images=len(images),
            # Empty .txt sidecars count as labels-on-disk so num_labels stays
            # consistent with the file tree.
            num_labels=labels_written + background_count,
            counts=counts,
            notes=notes,
            extra={
                "ratios": ratios,
                "data_yaml": "data.yaml",
                "treat_unlabeled_as_background": treat_unlabeled_as_background,
                "background_count": background_count,
                "unlabeled_count": unlabeled_count,
            },
        )


class YoloDetectionConverter(_YoloFileConverter):
    format_id = "yolo-det"


class YoloSegmentationConverter(_YoloFileConverter):
    format_id = "yolo-seg"
