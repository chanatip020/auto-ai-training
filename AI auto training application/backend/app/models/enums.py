"""Python-side mirrors of the Postgres enum types."""
from __future__ import annotations
from enum import Enum


class _StrEnum(str, Enum):
    """Backport of 3.11's enum.StrEnum so this module loads on 3.10 too."""
    def __str__(self) -> str:
        return self.value


class ProjectStatus(_StrEnum):
    CREATED = "created"
    DATASET_UPLOADED = "dataset_uploaded"
    DATASET_ANALYZED = "dataset_analyzed"
    READY_FOR_TRAINING = "ready_for_training"
    TRAINING = "training"
    COMPLETED = "completed"
    FAILED = "failed"


class ModelFamily(_StrEnum):
    YOLO = "yolo"


class TaskType(_StrEnum):
    DETECTION = "detection"
    SEGMENTATION = "segmentation"
    CLASSIFICATION = "classification"


class DatasetSource(_StrEnum):
    UPLOAD = "upload"
    CVAT = "cvat"
    MANUAL = "manual"


class JobStatus(_StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobKind(_StrEnum):
    INGEST_ZIP = "ingest_zip"
    INGEST_FILES = "ingest_files"
    CONVERT = "convert"
    ANALYZE = "analyze"
    TRAIN = "train"
    CVAT_IMPORT = "cvat_import"


class ArtifactKind(_StrEnum):
    WEIGHTS = "weights"
    PLOT = "plot"
    LOG = "log"
    EXPORT = "export"
    OTHER = "other"
