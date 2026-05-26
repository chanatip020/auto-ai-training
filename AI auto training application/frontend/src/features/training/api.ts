import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiUrl } from '../../lib/api';
import type {
  ExportFormat,
  ExportResult,
  PredictionResult,
  TrainingArtifact,
  TrainingJob,
  TrainingMetric,
} from '../../lib/types';

// Re-exported so TryItPanel can pull the types from this module.
export type { PredictionResult, ExportResult, ExportFormat } from '../../lib/types';

interface TrainingJobListOut { items: TrainingJob[]; total: number }
interface TrainingMetricsOut { items: TrainingMetric[] }
interface TrainingArtifactsOut { items: TrainingArtifact[] }

interface StartBody {
  dataset_version_id: string;
  params: Record<string, unknown>;
  // Phase 8 - provenance fields. All optional; backend supplies sensible defaults.
  preset_source?: 'recommended' | 'default' | 'manual';
  override_blockers?: boolean;
  recommendation_snapshot?: Record<string, unknown> | null;
}

export function useStartTraining(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: StartBody) =>
      api.post<TrainingJob>(`/api/v1/projects/${projectId}/training-jobs`, body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['training-jobs', projectId] }),
  });
}

export function useTrainingJobs(projectId: string | undefined) {
  return useQuery({
    queryKey: ['training-jobs', projectId],
    queryFn: () => api.get<TrainingJobListOut>(`/api/v1/projects/${projectId}/training-jobs`),
    enabled: !!projectId,
  });
}

export function useTrainingJob(jobId: string | undefined) {
  return useQuery({
    queryKey: ['training-job', jobId],
    queryFn: () => api.get<TrainingJob>(`/api/v1/training-jobs/${jobId}`),
    enabled: !!jobId,
    refetchInterval: (q) => {
      const d = q.state.data as TrainingJob | undefined;
      if (!d) return 2000;
      return d.status === 'pending' || d.status === 'running' ? 2000 : false;
    },
  });
}

export function useTrainingMetrics(jobId: string | undefined) {
  return useQuery({
    queryKey: ['training-metrics', jobId],
    queryFn: () => api.get<TrainingMetricsOut>(`/api/v1/training-jobs/${jobId}/metrics`),
    enabled: !!jobId,
  });
}

export function useArtifacts(jobId: string | undefined) {
  return useQuery({
    queryKey: ['training-artifacts', jobId],
    queryFn: () => api.get<TrainingArtifactsOut>(`/api/v1/training-jobs/${jobId}/artifacts`),
    enabled: !!jobId,
  });
}

export function useStopTraining(jobId: string) {
  return useMutation({
    mutationFn: () => api.post<TrainingJob>(`/api/v1/training-jobs/${jobId}/stop`),
  });
}

export function artifactDownloadUrl(jobId: string, artifactId: string): string {
  return apiUrl(`/api/v1/training-jobs/${jobId}/artifacts/${artifactId}/download`);
}

export function sseTrainingPath(jobId: string): string {
  return `/api/v1/sse/training/${jobId}`;
}

// ---- Phase 8 history ----

export interface TrainingHistoryItem {
  id: string;
  dataset_version_id: string;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'cancelled';
  best_metric: number | null;
  total_epochs: number | null;
  current_epoch: number | null;
  params: Record<string, unknown>;
  summary: Record<string, unknown>;
  preset_source: string | null;
  override_blockers: boolean;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}
interface HistoryOut { items: TrainingHistoryItem[]; total: number }

export function useTrainingHistory(
  projectId: string | undefined,
  opts: { limit?: number; offset?: number; status?: string } = {},
) {
  const qs = new URLSearchParams();
  if (opts.limit) qs.set('limit', String(opts.limit));
  if (opts.offset) qs.set('offset', String(opts.offset));
  if (opts.status) qs.set('status_filter', opts.status);
  const url = `/api/v1/projects/${projectId}/training-history${qs.toString() ? '?' + qs : ''}`;
  return useQuery({
    queryKey: ['training-history', projectId, opts],
    queryFn: () => api.get<HistoryOut>(url),
    enabled: !!projectId,
  });
}

export interface CloneConfig {
  dataset_version_id: string;
  params: Record<string, unknown>;
  preset_source: string | null;
  override_blockers: boolean;
}

export function useCloneAsConfig(jobId: string | undefined) {
  return useQuery({
    queryKey: ['clone-config', jobId],
    queryFn: () => api.get<CloneConfig>(`/api/v1/training-jobs/${jobId}/clone-as-config`),
    enabled: !!jobId,
  });
}

/* ---------- Phase 10: inference + export ---------- */

interface PredictArgs {
  file: File;
  conf: number;
  iou: number;
  imgsz?: number;
}

/**
 * Run prediction on one image against the trained model's best.pt.
 * The file is uploaded as multipart; conf/iou/imgsz go on the query string
 * (FastAPI treats primitives next to File() params as query parameters).
 */
export function usePredict(jobId: string) {
  return useMutation({
    mutationFn: ({ file, conf, iou, imgsz }: PredictArgs) => {
      const fd = new FormData();
      fd.append('file', file);
      const qs = new URLSearchParams({
        conf: String(conf),
        iou: String(iou),
      });
      if (imgsz !== undefined) qs.set('imgsz', String(imgsz));
      return api.upload<PredictionResult>(
        `/api/v1/training-jobs/${jobId}/predict?${qs.toString()}`,
        fd,
      );
    },
  });
}

/**
 * Export the trained model (best.pt) to a portable format. The server
 * returns an artifact record; the file shows up in the job's artifacts list.
 */
export function useExportModel(jobId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (format: ExportFormat) =>
      api.post<ExportResult>(`/api/v1/training-jobs/${jobId}/export`, { format }),
    onSuccess: () =>
      qc.invalidateQueries({ queryKey: ['training-artifacts', jobId] }),
  });
}
