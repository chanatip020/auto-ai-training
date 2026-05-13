"""Individual dataset checks."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from app.services.datasets.detect import IMAGE_EXTS


@dataclass
class CountReport:
    image_count: int = 0
    label_count: int = 0
    per_split: dict[str, int] = field(default_factory=dict)


@dataclass
class LabelHealthReport:
    missing: int = 0
    empty: int = 0
    image_count: int = 0
    missing_ratio: float = 0.0
    empty_ratio: float = 0.0


@dataclass
class ClassDistributionReport:
    counts: dict[str, int] = field(default_factory=dict)
    images_per_class: dict[str, int] = field(default_factory=dict)
    classes: list[str] = field(default_factory=list)
    gini: float = 0.0


@dataclass
class ResolutionReport:
    sampled: int = 0
    widths_median: int | None = None
    heights_median: int | None = None
    p10_width: int | None = None
    p90_width: int | None = None
    too_small: int = 0
    too_large: int = 0


@dataclass
class DuplicateReport:
    duplicate_groups: int = 0
    duplicate_images: int = 0
    sample_groups: list[list[str]] = field(default_factory=list)


@dataclass
class CorruptionReport:
    corrupt: list[str] = field(default_factory=list)
    sampled: int = 0


def _images_in_dir(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS]


def _read_classes(version_root: Path) -> list[str]:
    yaml_path = version_root / "data.yaml"
    if yaml_path.exists():
        try:
            import yaml
            doc = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            names = doc.get("names")
            if isinstance(names, list):
                return [str(n) for n in names]
            if isinstance(names, dict):
                return [names[k] for k in sorted(names)]
        except Exception:
            pass
    return []


def _iter_split_pairs(version_root: Path):
    for split in ("train", "val", "test"):
        img_dir = version_root / "images" / split
        lbl_dir = version_root / "labels" / split
        if not img_dir.exists():
            continue
        for img in _images_in_dir(img_dir):
            lbl = lbl_dir / (img.stem + ".txt")
            yield split, img, lbl if lbl.exists() else None


def _is_cls_layout(version_root: Path) -> bool:
    return (
        (version_root / "train").is_dir()
        and not (version_root / "images").is_dir()
        and not (version_root / "labels").is_dir()
    )


def count_files(version_root: Path) -> CountReport:
    rep = CountReport()
    if _is_cls_layout(version_root):
        for split in ("train", "val", "test"):
            split_dir = version_root / split
            if not split_dir.exists():
                continue
            n = sum(1 for p in split_dir.rglob("*")
                    if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
            rep.per_split[split] = n
            rep.image_count += n
        rep.label_count = rep.image_count
        return rep
    seen_splits: dict[str, int] = defaultdict(int)
    labels = 0
    for split, _img, lbl in _iter_split_pairs(version_root):
        seen_splits[split] += 1
        rep.image_count += 1
        if lbl is not None:
            labels += 1
    rep.label_count = labels
    rep.per_split = dict(seen_splits)
    return rep


def label_health(version_root: Path) -> LabelHealthReport:
    if _is_cls_layout(version_root):
        return LabelHealthReport()
    rep = LabelHealthReport()
    for _, _img, lbl in _iter_split_pairs(version_root):
        rep.image_count += 1
        if lbl is None:
            rep.missing += 1
        else:
            try:
                content = lbl.read_text(encoding="utf-8").strip()
                if not content:
                    rep.empty += 1
            except Exception:
                rep.empty += 1
    if rep.image_count:
        rep.missing_ratio = rep.missing / rep.image_count
        rep.empty_ratio = rep.empty / rep.image_count
    return rep


def class_distribution(version_root: Path) -> ClassDistributionReport:
    rep = ClassDistributionReport()
    classes = _read_classes(version_root)
    rep.classes = classes

    if _is_cls_layout(version_root):
        all_classes: set[str] = set()
        counts: Counter[str] = Counter()
        for split in ("train", "val", "test"):
            split_dir = version_root / split
            if not split_dir.exists():
                continue
            for class_dir in split_dir.iterdir():
                if class_dir.is_dir():
                    n = sum(1 for p in class_dir.rglob("*")
                            if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
                    counts[class_dir.name] += n
                    all_classes.add(class_dir.name)
        rep.classes = sorted(all_classes) if not classes else classes
        rep.counts = dict(counts)
        rep.images_per_class = dict(counts)
    else:
        ann_counts: Counter[int] = Counter()
        img_classes: dict[int, set[str]] = defaultdict(set)
        for _, img, lbl in _iter_split_pairs(version_root):
            if lbl is None:
                continue
            try:
                for line in lbl.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    cls_idx = int(line.split()[0])
                    ann_counts[cls_idx] += 1
                    img_classes[cls_idx].add(str(img))
            except (ValueError, IndexError):
                continue
        if classes:
            rep.counts = {classes[i] if i < len(classes) else f"class_{i}": v
                          for i, v in ann_counts.items()}
            rep.images_per_class = {classes[i] if i < len(classes) else f"class_{i}": len(s)
                                    for i, s in img_classes.items()}
        else:
            rep.counts = {f"class_{i}": v for i, v in ann_counts.items()}
            rep.images_per_class = {f"class_{i}": len(s) for i, s in img_classes.items()}

    rep.gini = _gini_imbalance(list(rep.counts.values()))
    return rep


def _gini_imbalance(values: list[int]) -> float:
    if not values:
        return 0.0
    s = sum(values)
    if s == 0:
        return 0.0
    n = len(values)
    if n == 1:
        return 0.0
    sorted_v = sorted(values)
    cum = sum((i + 1) * v for i, v in enumerate(sorted_v))
    return (2.0 * cum) / (n * s) - (n + 1.0) / n


def _percentile(sorted_vals: list[int], q: float) -> int | None:
    if not sorted_vals:
        return None
    k = int(round((len(sorted_vals) - 1) * q))
    return sorted_vals[k]


def _all_images(version_root: Path) -> list[Path]:
    out: list[Path] = []
    if _is_cls_layout(version_root):
        for split in ("train", "val", "test"):
            d = version_root / split
            if d.exists():
                out.extend(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    else:
        for split in ("train", "val", "test"):
            d = version_root / "images" / split
            if d.exists():
                out.extend(p for p in d.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    return out


def resolution_stats(version_root: Path, *, sample_limit: int = 500) -> ResolutionReport:
    rep = ResolutionReport()
    images = _all_images(version_root)
    sample = images[:sample_limit]
    widths: list[int] = []
    heights: list[int] = []
    for img_path in sample:
        try:
            with Image.open(img_path) as im:
                w, h = im.size
        except (UnidentifiedImageError, OSError):
            continue
        widths.append(w)
        heights.append(h)
        m_min = min(w, h)
        m_max = max(w, h)
        if m_min < 32:
            rep.too_small += 1
        if m_max > 4096:
            rep.too_large += 1
    rep.sampled = len(widths)
    if widths:
        widths.sort(); heights.sort()
        rep.widths_median = _percentile(widths, 0.5)
        rep.heights_median = _percentile(heights, 0.5)
        rep.p10_width = _percentile(widths, 0.10)
        rep.p90_width = _percentile(widths, 0.90)
    return rep


_HASH_ALL_BITS = (1 << 64) - 1


def _ahash64(path: Path) -> int | None:
    try:
        with Image.open(path) as im:
            small = im.convert("L").resize((8, 8), Image.BILINEAR)
            pixels = list(small.getdata())
    except (UnidentifiedImageError, OSError):
        return None
    if min(pixels) == max(pixels):
        return None
    avg = sum(pixels) / 64.0
    h = 0
    for i, p in enumerate(pixels):
        if p >= avg:
            h |= 1 << i
    if h == 0 or h == _HASH_ALL_BITS:
        return None
    return h


def duplicates(version_root: Path, *, sample_limit: int = 1000) -> DuplicateReport:
    rep = DuplicateReport()
    images = _all_images(version_root)[:sample_limit]
    bucket: dict[int, list[str]] = defaultdict(list)
    for p in images:
        h = _ahash64(p)
        if h is not None:
            bucket[h].append(p.name)
    groups = [g for g in bucket.values() if len(g) > 1]
    rep.duplicate_groups = len(groups)
    rep.duplicate_images = sum(len(g) for g in groups)
    rep.sample_groups = [g[:6] for g in groups[:5]]
    return rep


def corruption(version_root: Path, *, sample_limit: int = 1000) -> CorruptionReport:
    rep = CorruptionReport()
    images = _all_images(version_root)[:sample_limit]
    for p in images:
        rep.sampled += 1
        try:
            with Image.open(p) as im:
                im.verify()
        except Exception:
            rep.corrupt.append(p.name)
    return rep


def run_all_checks(version_root: Path) -> dict[str, dict]:
    counts = count_files(version_root)
    health = label_health(version_root)
    classes = class_distribution(version_root)
    res = resolution_stats(version_root)
    dup = duplicates(version_root)
    corr = corruption(version_root)
    return {
        "counts": counts.__dict__,
        "label_health": health.__dict__,
        "class_distribution": {**classes.__dict__},
        "resolution": res.__dict__,
        "duplicates": dup.__dict__,
        "corruption": corr.__dict__,
    }
