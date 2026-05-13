"""Converter registry.

Each task_type maps to a converter class that takes a normalized 'raw'
dataset layout and produces a fully-formed training-ready folder tree.
"""
from __future__ import annotations

from app.models.enums import TaskType
from app.services.datasets.converters.base import BaseConverter, ConversionResult
from app.services.datasets.converters.yolo import YoloDetectionConverter, YoloSegmentationConverter
from app.services.datasets.converters.yolo_cls import YoloClassificationConverter

# format string -> converter class
FORMAT_TO_CONVERTER: dict[str, type[BaseConverter]] = {
    "yolo-det": YoloDetectionConverter,
    "yolo-seg": YoloSegmentationConverter,
    "yolo-cls": YoloClassificationConverter,
}

# task_type -> default format string
DEFAULT_FORMAT_FOR_TASK: dict[TaskType, str] = {
    TaskType.DETECTION: "yolo-det",
    TaskType.SEGMENTATION: "yolo-seg",
    TaskType.CLASSIFICATION: "yolo-cls",
}


def get_converter(format: str) -> BaseConverter:
    cls = FORMAT_TO_CONVERTER.get(format)
    if cls is None:
        raise KeyError(format)
    return cls()


__all__ = [
    "BaseConverter",
    "ConversionResult",
    "FORMAT_TO_CONVERTER",
    "DEFAULT_FORMAT_FOR_TASK",
    "get_converter",
]
