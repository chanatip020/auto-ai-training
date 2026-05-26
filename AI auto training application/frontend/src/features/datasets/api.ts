import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, downloadWithAuth } from '../../lib/api';
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

interface CreateDatasetArgs {
  name: string;
  treat_unlabeled_as_background?: boolean;
}

export function useCreateDataset(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (args: string | CreateDatasetArgs) => {
      const body =
        typeof args === 'string'
          ? { name: args, source: 'upload' as const }
          : {
              name: args.name,
              source: 'upload' as const,
              treat_unlabeled_as_background: args.treat_unlabeled_as_background ?? false,
            };
      return api.post<Dataset>(`/api/v1/projects/${projectId}/datasets`, body);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['datasets', projectId] }),
  });
}

export function useUpdateDataset() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      datasetId,
      body,
    }: {
      datasetId: string;
      body: { treat_unlabeled_as_background?: boolean };
    }) => api.patch<Dataset>(`/api/v1/datasets/${datasetId}`, body),
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ['dataset', d.id] });
      qc.invalidateQueries({ queryKey: ['datasets', d.project_id] });
    },
  });
}

// `datasetId` is read at mutate time (not hook-setup time) so that flows
// which create the dataset right before the upload don't end up with a
// stale empty-string closure.
export function useUploadZip() {
  return useMutation({
    mutationFn: ({ datasetId, file }: { datasetId: string; file: File }) => {
      if (!datasetId) throw new Error('datasetId is required');
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
  treat_unlabeled_as_background?: boolean | null;
}

export function useConvert() {
  return useMutation({
    mutationFn: ({ datasetId, body }: { datasetId: string; body: ConvertBody }) => {
      if (!datasetId) throw new Error('datasetId is required');
      return api.post<{ job_id: string }>(`/api/v1/datasets/${datasetId}/convert`, body);
    },
  });
}

/**
 * Download a converted dataset version as a ZIP. The backend streams
 * images/, labels/, and data.yaml — drop-in usable by Ultralytics YOLO.
 * Raw versions are not exportable (400 EXPORT_RAW_NOT_SUPPORTED).
 */
export function useExportVersion() {
  return useMutation({
    mutationFn: ({
      versionId,
      filename,
    }: {
      versionId: string;
      filename: string;
    }) =>
      downloadWithAuth(
        `/api/v1/datasets/versions/${versionId}/export`,
        filename,
      ),
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
