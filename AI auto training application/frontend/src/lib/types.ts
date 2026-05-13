/* DTO shapes that mirror the backend's Pydantic schemas. Keep in sync with
   backend/app/schemas/*. */

export type ProjectStatus =
  | 'created'
  | 'dataset_uploaded'
  | 'dataset_analyzed'
  | 'ready_for_training'
  | 'training'
  | 'completed'
  | 'failed';

export type ModelFamily = 'yolo';
export type TaskType = 'detection' | 'segmentation' | 'classification';

export interface Project {
  id: string;
  name: string;
  description: string | null;
  model_family: ModelFamily;
  task_type: TaskType;
  status: ProjectStatus;
  created_at: string;
  updated_at: string;
}

export interface Dataset {
  id: string;
  project_id: string;
  name: string;
  source: 'upload' | 'cvat' | 'manual';
  created_at: string;
}

export interface DatasetVersion {
  id: string;
  dataset_id: string;
  version: number;
  format: string;          // 'raw' | 'yolo-det' | 'yolo-seg' | 'yolo-cls'
  storage_uri: string;
  num_images: number | null;
  num_labels: number | null;
  num_classes: number | null;
  classes: string[] | null;
  summary: Record<string, unknown>;
  created_at: string;
}

export interface DatasetDetail {
  dataset: Dataset;
  versions: DatasetVersion[];
}

export type JobStatus = 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';

export interface JobOut {
  id: string;
  kind: string;
  status: JobStatus;
  project_id: string | null;
  dataset_id: string | null;
  payload: Record<string, unknown>;
  progress: number;
  message: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface AuditLogItem {
  id: number;
  project_id: string;
  event: string;
  payload: Record<string, unknown>;
  actor: string | null;
  created_at: string;
}

export interface RecommendationItem {
  code: string;
  severity: 'blocker' | 'warning' | 'info';
  message: string;
  fix: string | null;
  meta: Record<string, unknown>;
}

export interface Analysis {
  id: string;
  dataset_version_id: string;
  health_score: number | null;
  findings: { checks?: Record<string, unknown>; components?: Record<string, number> };
  recommendations: RecommendationItem[];
  ready_for_training: boolean;
  created_at: string;
}

export interface TrainingRecommendation {
  model_family: string;
  task_type: string;
  params: Record<string, unknown>;
  reasons: Record<string, string>;
  assumptions: Record<string, unknown>;
}

export interface TrainingJob {
  id: string;
  project_id: string;
  dataset_version_id: string;
  status: JobStatus;
  progress: number;
  current_epoch: number | null;
  total_epochs: number | null;
  best_metric: number | null;
  params: Record<string, unknown>;
  message: string | null;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export interface TrainingMetric {
  epoch: number;
  loss: number | null;
  val_loss: number | null;
  precision: number | null;
  recall: number | null;
  map50: number | null;
  map5095: number | null;
  extra: Record<string, unknown>;
  recorded_at: string;
}

export interface TrainingArtifact {
  id: string;
  name: string;
  kind: 'weights' | 'plot' | 'log' | 'export' | 'other';
  storage_uri: string;
  size_bytes: number | null;
  created_at: string;
}

/* ---------- CVAT (Phase 6 — types defined now so the rest of the
              codebase can already reference them) ---------- */

export interface CvatConnection {
  id: string;
  name: string;
  base_url: string;
  username: string;
  created_at: string;
  last_used_at: string | null;
}

export interface CvatImport {
  id: string;
  project_id: string;
  connection_id: string;
  source_type: 'cvat_project' | 'cvat_task';
  source_id: number;
  status: JobStatus;
  progress: number;
  message: string | null;
  error: string | null;
  created_at: string;
}

/* ---------- API envelope ---------- */
export interface Envelope<T> {
  data: T | null;
  error: { code: string; message: string; details: Record<string, unknown> } | null;
  meta: { request_id: string | null; timestamp: string };
}
