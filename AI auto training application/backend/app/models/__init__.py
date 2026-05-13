"""Side-effect import: registers every model on Base.metadata."""
from app.models.analysis import Analysis  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.base import Base  # noqa: F401
from app.models.dataset import Dataset, DatasetVersion  # noqa: F401
from app.models.enums import (  # noqa: F401
    ArtifactKind,
    DatasetSource,
    JobKind,
    JobStatus,
    ModelFamily,
    ProjectStatus,
    TaskType,
)
from app.models.job import Job  # noqa: F401
from app.models.project import Project  # noqa: F401
from app.models.training import TrainingArtifact, TrainingJob, TrainingMetric  # noqa: F401
from app.models.user import User  # noqa: F401


def register_all() -> None:
    return None
