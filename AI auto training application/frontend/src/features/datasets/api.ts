import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { Dataset, DatasetDetail, JobOut } from '../../lib/types';

interface DatasetListOut { items: Dataset[]; total: number }

export function useDatasets(projectId: string | undefined) {
  return useQuery({
    queryKey: ['datasets', projectId],
    queryFn: () => api.get<DatasetListOut>(`/api/v1/projects/${projectId}/datasets`),
    enabled: !!projectId,
  });
}

export function useDatasetDetail(datasetId: string | undefined) {
  return useQuery({
    queryKey: ['dataset', datasetId],
    queryFn: () => api.get<DatasetDetail>(`/api/v1/datasets/${datasetId}`),
    enabled: !!datasetId,
  });
}

export function useCreateDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) =>
      api.post<Dataset>(`/api/v1/projects/${projectId}/datasets`, { name, source: 'upload' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['datasets', projectId] }),
  });
}

export function useUploadZip(datasetId: string) {
  return useMutation({
    mutationFn: (file: File) => {
      const fd = new FormData();
      fd.append('file', file);
      return api.upload<{ job_id: string }>(`/api/v1/datasets/${datasetId}/upload-zip`, fd);
    },
  });
}

interface ConvertBody {
  format: 'yolo-det' | 'yolo-seg' | 'yolo-cls';
  ratios?: { train: number; val: number; test: number };
  classes_override?: string[] | null;
}

export function useConvert(datasetId: string) {
  return useMutation({
    mutationFn: (body: ConvertBody) =>
      api.post<{ job_id: string }>(`/api/v1/datasets/${datasetId}/convert`, body),
  });
}

export function useJob(jobId: string | null) {
  return useQuery({
    queryKey: ['job', jobId],
    queryFn: () => api.get<JobOut>(`/api/v1/jobs/${jobId}`),
    enabled: !!jobId,
    // Poll every second while pending/running
    refetchInterval: (q) => {
      const d = q.state.data as JobOut | undefined;
      if (!d) return 1000;
      return d.status === 'pending' || d.status === 'running' ? 1000 : false;
    },
  });
}
