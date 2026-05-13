import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../../lib/api';
import type {
  AuditLogItem,
  ModelFamily,
  Project,
  ProjectStatus,
  TaskType,
} from '../../lib/types';

interface ProjectListOut { items: Project[]; total: number }
interface TimelineOut { items: AuditLogItem[] }

export function useProjects(status?: ProjectStatus) {
  return useQuery({
    queryKey: ['projects', status ?? 'all'],
    queryFn: () => api.get<ProjectListOut>(
      '/api/v1/projects' + (status ? `?status=${status}` : ''),
    ),
  });
}

export function useProject(id: string | undefined) {
  return useQuery({
    queryKey: ['project', id],
    queryFn: () => api.get<Project>(`/api/v1/projects/${id}`),
    enabled: !!id,
  });
}

export function useTimeline(id: string | undefined) {
  return useQuery({
    queryKey: ['project-timeline', id],
    queryFn: () => api.get<TimelineOut>(`/api/v1/projects/${id}/timeline`),
    enabled: !!id,
  });
}

interface CreatePayload {
  name: string;
  description?: string;
  model_family: ModelFamily;
  task_type: TaskType;
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: CreatePayload) => api.post<Project>('/api/v1/projects', body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.del<void>(`/api/v1/projects/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['projects'] }),
  });
}
