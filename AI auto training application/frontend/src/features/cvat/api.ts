import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type { CvatConnection, CvatImport } from '../../lib/types';

interface ConnectionListOut { items: CvatConnection[]; total: number }

export interface CvatProjectSummary {
  id: number;
  name: string;
  status: string | null;
  tasks_count: number | null;
  updated_date: string | null;
}
export interface CvatTaskSummary {
  id: number;
  name: string;
  status: string | null;
  size: number | null;
  project_id: number | null;
  updated_date: string | null;
}


// ---- connections CRUD ----

export function useCvatConnections() {
  return useQuery({
    queryKey: ['cvat-connections'],
    queryFn: () => api.get<ConnectionListOut>('/api/v1/cvat/connections'),
  });
}

export interface CreateConnectionBody {
  name: string;
  base_url: string;
  username: string;
  secret: string;
}

export function useCreateConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreateConnectionBody) =>
      api.post<CvatConnection>('/api/v1/cvat/connections', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvat-connections'] }),
  });
}

export function useDeleteConnection() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`/api/v1/cvat/connections/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['cvat-connections'] }),
  });
}

export function useTestConnection() {
  return useMutation({
    mutationFn: (id: string) =>
      api.post<{ ok: boolean; server: string }>(`/api/v1/cvat/connections/${id}/test`),
  });
}


// ---- proxied listings ----

export function useCvatProjects(connectionId: string | null) {
  return useQuery({
    queryKey: ['cvat-projects', connectionId],
    queryFn: () => api.get<CvatProjectSummary[]>(
      `/api/v1/cvat/connections/${connectionId}/projects`,
    ),
    enabled: !!connectionId,
  });
}

export function useCvatTasks(connectionId: string | null, projectId: number | null) {
  return useQuery({
    queryKey: ['cvat-tasks', connectionId, projectId],
    queryFn: () => {
      const qs = projectId != null ? `?project_id=${projectId}` : '';
      return api.get<CvatTaskSummary[]>(
        `/api/v1/cvat/connections/${connectionId}/tasks${qs}`,
      );
    },
    enabled: !!connectionId,
  });
}


// ---- imports ----

export interface StartCvatImportBody {
  connection_id: string;
  source_type: 'cvat_project' | 'cvat_task';
  source_id: number;
  source_name?: string;
  auto_convert?: boolean;
}

export function useStartCvatImport(projectId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: StartCvatImportBody) =>
      api.post<CvatImport>(`/api/v1/projects/${projectId}/cvat-imports`, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['datasets', projectId] });
      qc.invalidateQueries({ queryKey: ['project-timeline', projectId] });
    },
  });
}

export function useCvatImport(importId: string | null) {
  return useQuery({
    queryKey: ['cvat-import', importId],
    queryFn: () => api.get<CvatImport>(`/api/v1/cvat-imports/${importId}`),
    enabled: !!importId,
    refetchInterval: (q) => {
      const d = q.state.data as CvatImport | undefined;
      if (!d) return 2000;
      return d.status === 'pending' || d.status === 'running' ? 2000 : false;
    },
  });
}
