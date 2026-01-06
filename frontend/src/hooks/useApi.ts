import { useMutation, useQuery as useRQQuery, useQueryClient } from '@tanstack/react-query';

import { del, get, post, put } from '@/lib/api';
import {
  CacheClearResponse,
  CacheStats,
  HealthResponse,
  QueryRequest,
  QueryResponse,
  Tenant,
  TenantStatus,
  VisualizationData,
  VisualizationExportPayload,
  VisualizationExportResponse,
  VisualizationNodeContext,
} from '@/types/api';
import { useQueryStore } from '@/stores/queryStore';
import { useTenantStore } from '@/stores/tenantStore';

type TenantMutationPayload = {
  tenant_id: string;
  name?: string;
  status?: TenantStatus;
  config?: Record<string, unknown>;
};

type CreateTenantPayload = TenantMutationPayload & {
  name: string;
};

type UseMetricsOptions = {
  refetchInterval?: number | false;
  enabled?: boolean;
};

export const useHealth = () =>
  useRQQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: () => get<HealthResponse>('/api/health'),
    staleTime: 60_000,
  });

export const useCacheStats = () =>
  useRQQuery<CacheStats>({
    queryKey: ['cache-stats'],
    queryFn: () => get<CacheStats>('/api/cache/stats'),
    refetchInterval: 30_000,
  });

export const useTenants = () => {
  const fetchTenants = useTenantStore((state) => state.fetchTenants);
  const tenants = useTenantStore((state) => state.tenants);
  const currentTenantId = useTenantStore((state) => state.currentTenantId);
  const setCurrentTenant = useTenantStore((state) => state.setCurrentTenant);

  const query = useRQQuery<Tenant[]>({
    queryKey: ['tenants'],
    queryFn: fetchTenants,
  });

  return {
    ...query,
    data: query.data ?? tenants,
    tenants,
    currentTenantId,
    setCurrentTenant,
  };
};

export const useQuery = () => {
  const addToHistory = useQueryStore((state) => state.addToHistory);
  const queryClient = useQueryClient();

  return useMutation<QueryResponse, Error, QueryRequest>({
    mutationKey: ['execute-query'],
    mutationFn: (variables) => post<QueryResponse>('/api/query', variables),
    onSuccess: (data, variables) => {
      addToHistory(variables, data);
      queryClient.invalidateQueries({ queryKey: ['cache-stats'] });
    },
  });
};

export const useVisualizationTrace = (traceId?: string) =>
  useRQQuery<VisualizationData>({
    queryKey: ['visualization', 'trace', traceId],
    queryFn: () => get<VisualizationData>(`/api/visualization/trace/${traceId}`),
    enabled: Boolean(traceId),
    staleTime: 30_000,
  });

export const useVisualizationVerification = (answerId?: string) =>
  useRQQuery<VisualizationData>({
    queryKey: ['visualization', 'verification', answerId],
    queryFn: () => get<VisualizationData>(`/api/visualization/verification/${answerId}`),
    enabled: Boolean(answerId),
    staleTime: 30_000,
  });

export const useVisualizationEvidence = (nodeId?: string) =>
  useRQQuery<VisualizationNodeContext>({
    queryKey: ['visualization', 'evidence', nodeId],
    queryFn: () => get<VisualizationNodeContext>(`/api/visualization/evidence/${nodeId}`),
    enabled: Boolean(nodeId),
    retry: 1,
  });

export const useExportVisualization = () =>
  useMutation<VisualizationExportResponse, Error, VisualizationExportPayload>({
    mutationKey: ['visualization', 'export'],
    mutationFn: (variables) => post<VisualizationExportResponse>('/api/visualization/export', variables),
  });

export const useCreateTenant = () => {
  const queryClient = useQueryClient();

  return useMutation<Tenant, Error, CreateTenantPayload>({
    mutationKey: ['tenants', 'create'],
    mutationFn: (payload) => post<Tenant>('/api/tenants', payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });
};

export const useUpdateTenant = () => {
  const queryClient = useQueryClient();

  return useMutation<Tenant, Error, TenantMutationPayload>({
    mutationKey: ['tenants', 'update'],
    mutationFn: ({ tenant_id, ...payload }) => put<Tenant>(`/api/tenants/${tenant_id}`, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });
};

export const useDeleteTenant = () => {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationKey: ['tenants', 'delete'],
    mutationFn: (tenantId) => del<void>(`/api/tenants/${tenantId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tenants'] });
    },
  });
};

export const useClearCache = () => {
  const queryClient = useQueryClient();

  return useMutation<CacheClearResponse, Error, { pattern?: string }>({
    mutationKey: ['cache', 'clear'],
    mutationFn: ({ pattern = '*' } = {}) => post<CacheClearResponse>('/api/cache/clear', { pattern }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['cache-stats'] });
    },
  });
};

export const useMetrics = (options?: UseMetricsOptions) =>
  useRQQuery<string>({
    queryKey: ['monitoring', 'metrics'],
    queryFn: () => get<string>('/monitoring/metrics'),
    staleTime: 5_000,
    refetchInterval: options?.refetchInterval,
    enabled: options?.enabled ?? true,
  });
