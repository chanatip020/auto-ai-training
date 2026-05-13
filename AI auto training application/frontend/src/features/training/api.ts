import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, apiUrl } from '../../lib/api';
import type {
  TrainingArtifact,
  TrainingJob,
  TrainingMetric,
} from '../../lib/types';

interface TrainingJobListOut { items: TrainingJob[]; total: number }
interface TrainingMetricsOut { items: TrainingMetric[] }
interface TrainingArtifactsOut { items: TrainingArtifact[] }

interface StartBody {
  dataset_version_id: string;
  params: Record<string, unknown>;
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
