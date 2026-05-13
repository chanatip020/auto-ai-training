"""Dataset layout detection.

Walks an on-disk folder and reports what kind of dataset it looks like.
Phase 2 reports a hint only; Phase 3's converters do the real work.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp", ".tif", ".tiff"}
LABEL_TEXT_EXTS = {".txt"}
LABEL_XML_EXTS = {".xml"}
LABEL_JSON_EXTS = {".json"}

# Filenames that look like .txt but are not annotation labels.
NON_LABEL_TXT = {"classes.txt", "names.txt", "labels.txt", "readme.txt"}


@dataclass
class LayoutReport:
    detected_format: str   # 'yolo' | 'coco' | 'voc' | 'images_only' | 'mixed' | 'empty'
    image_count: int
    label_count: int
    classes_hint: list[str]
    notes: list[str]


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p


def _read_yolo_classes(root: Path) -> list[str]:
    """Best-effort classes.txt / data.yaml class extraction."""
    for name in ("classes.txt", "names.txt"):
        f = root / name
        if f.exists():
            try:
                return [line.strip() for line in f.read_text(encoding="utf-8").splitlines() if line.strip()]
            except Exception:
                pass
    yml = root / "data.yaml"
    if yml.exists():
        try:
            text = yml.read_text(encoding="utf-8")
            for line in text.splitlines():
                if line.strip().startswith("names:"):
                    return [t.strip(" []'\"") for t in line.split(":", 1)[1].split(",") if t.strip(" []'\"")]
        except Exception:
            pass
    return []


def detect(root: Path) -> LayoutReport:
    images = 0
    txt_labels = 0
    xml_labels = 0
    json_labels = 0
    notes: list[str] = []

    if not root.exists():
        return LayoutReport("empty", 0, 0, [], ["folder does not exist"])

    has_coco_json = False

    for f in _iter_files(root):
        ext = f.suffix.lower()
        name = f.name.lower()
        if ext in IMAGE_EXTS:
            images += 1
        elif ext in LABEL_TEXT_EXTS and name not in NON_LABEL_TXT:
            txt_labels += 1
        elif ext in LABEL_XML_EXTS:
            xml_labels += 1
        elif ext in LABEL_JSON_EXTS and ("annot" in name or name in {"instances.json", "annotations.json"}):
            json_labels += 1
            has_coco_json = True

    classes: list[str] = []

    if images == 0 and txt_labels == 0 and xml_labels == 0 and json_labels == 0:
        return LayoutReport("empty", 0, 0, [], ["no recognised files found"])

    if has_coco_json:
        fmt = "coco"
    elif xml_labels > 0 and xml_labels > images * 0.3:
        fmt = "voc"
    elif txt_labels > 0:
        fmt = "yolo"
        classes = _read_yolo_classes(root)
        if not classes:
            notes.append("no classes.txt / data.yaml found - class names will need to be provided")
    elif images > 0:
        fmt = "images_only"
        notes.append("no annotations detected - dataset is images-only")
    else:
        fmt = "mixed"

    total_labels = txt_labels + xml_labels + json_labels

    if fmt == "yolo" and images > 0 and txt_labels < images * 0.5:
        missing = images - txt_labels
        notes.append("many images appear to be missing labels (" + str(missing) + " of " + str(images) + ")")

    return LayoutReport(
        detected_format=fmt,
        image_count=images,
        label_count=total_labels,
        classes_hint=classes,
        notes=notes,
    )
