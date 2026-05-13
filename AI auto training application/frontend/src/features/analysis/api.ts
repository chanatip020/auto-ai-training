import { useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { Analysis, TrainingRecommendation } from '../../lib/types';

export function useStartAnalysis(versionId: string) {
  return useMutation({
    mutationFn: () => api.post<{ job_id: string }>(
      `/api/v1/dataset-versions/${versionId}/analyze`,
    ),
  });
}

export function useAnalysis(versionId: string | undefined) {
  return useQuery({
    queryKey: ['analysis', versionId],
    queryFn: () => api.get<Analysis>(`/api/v1/dataset-versions/${versionId}/analysis`),
    enabled: !!versionId,
    retry: 0,        // 404 just means "not run yet"
  });
}

export function useTrainingRecommendation(versionId: string | undefined) {
  return useQuery({
    queryKey: ['training-rec', versionId],
    queryFn: () =>
      api.post<TrainingRecommendation>(
        `/api/v1/dataset-versions/${versionId}/training-recommendation`,
        { gpu_mem_gb: 0 }, // CPU-only per the locked-in stack
      ),
    enabled: !!versionId,
    retry: 0,
  });
}
