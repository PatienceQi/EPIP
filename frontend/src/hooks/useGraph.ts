/**
 * Graph API React hooks
 */

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { del, get, post, put } from '@/lib/api';
import type {
  CreateNodeRequest,
  CreateRelationshipRequest,
  CypherExecuteRequest,
  CypherExecuteResponse,
  ExpandNodeRequest,
  GraphData,
  GraphHealthResponse,
  GraphNode,
  GraphRelationship,
  GraphStats,
  ImportNodesRequest,
  ImportRelationshipsRequest,
  ImportResponse,
  LinkPredictionRequest,
  LinkPredictionResponse,
  MaintenanceResponse,
  NodesListResponse,
  SearchNodesRequest,
  UpdateNodeRequest,
} from '@/types/graph';

// Query keys
export const graphKeys = {
  all: ['graph'] as const,
  nodes: () => [...graphKeys.all, 'nodes'] as const,
  nodesList: (params: { label?: string; limit?: number; offset?: number }) =>
    [...graphKeys.nodes(), params] as const,
  node: (id: string) => [...graphKeys.nodes(), id] as const,
  nodeRelationships: (id: string) => [...graphKeys.node(id), 'relationships'] as const,
  nodeExpand: (id: string) => [...graphKeys.node(id), 'expand'] as const,
  labels: () => [...graphKeys.all, 'labels'] as const,
  relationshipTypes: () => [...graphKeys.all, 'relationship-types'] as const,
  stats: () => [...graphKeys.all, 'stats'] as const,
  health: () => [...graphKeys.all, 'health'] as const,
  search: (query: string) => [...graphKeys.all, 'search', query] as const,
};

// Node queries
export const useGraphNodes = (params?: { label?: string; limit?: number; offset?: number }) =>
  useQuery({
    queryKey: graphKeys.nodesList(params ?? {}),
    queryFn: () => {
      const searchParams = new URLSearchParams();
      if (params?.label) searchParams.set('label', params.label);
      if (params?.limit) searchParams.set('limit', String(params.limit));
      if (params?.offset) searchParams.set('offset', String(params.offset));
      const queryString = searchParams.toString();
      return get<NodesListResponse>(`/api/graph/nodes${queryString ? `?${queryString}` : ''}`);
    },
  });

export const useGraphNode = (nodeId: string | undefined) =>
  useQuery({
    queryKey: graphKeys.node(nodeId ?? ''),
    queryFn: () => get<GraphNode>(`/api/graph/nodes/${nodeId}`),
    enabled: Boolean(nodeId),
  });

export const useNodeRelationships = (nodeId: string | undefined, direction?: string) =>
  useQuery({
    queryKey: graphKeys.nodeRelationships(nodeId ?? ''),
    queryFn: () => {
      const params = direction ? `?direction=${direction}` : '';
      return get<GraphRelationship[]>(`/api/graph/nodes/${nodeId}/relationships${params}`);
    },
    enabled: Boolean(nodeId),
  });

export const useExpandNode = (nodeId: string | undefined, depth = 1) =>
  useQuery({
    queryKey: graphKeys.nodeExpand(nodeId ?? ''),
    queryFn: () =>
      post<GraphData>(`/api/graph/nodes/${nodeId}/expand`, { depth } as ExpandNodeRequest),
    enabled: Boolean(nodeId),
  });

// Metadata queries
export const useGraphLabels = () =>
  useQuery({
    queryKey: graphKeys.labels(),
    queryFn: () => get<string[]>('/api/graph/labels'),
    staleTime: 60_000,
  });

export const useGraphRelationshipTypes = () =>
  useQuery({
    queryKey: graphKeys.relationshipTypes(),
    queryFn: () => get<string[]>('/api/graph/relationship-types'),
    staleTime: 60_000,
  });

export const useGraphStats = () =>
  useQuery({
    queryKey: graphKeys.stats(),
    queryFn: () => get<GraphStats>('/api/graph/stats'),
    staleTime: 30_000,
  });

export const useGraphHealth = () =>
  useQuery({
    queryKey: graphKeys.health(),
    queryFn: () => get<GraphHealthResponse>('/api/admin/graph/health'),
    staleTime: 10_000,
  });

// Search
export const useSearchNodes = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: SearchNodesRequest) =>
      post<GraphNode[]>('/api/graph/search', request),
    onSuccess: (data, variables) => {
      queryClient.setQueryData(graphKeys.search(variables.query), data);
    },
  });
};

// Cypher execution
export const useExecuteCypher = () =>
  useMutation({
    mutationFn: (request: CypherExecuteRequest) =>
      post<CypherExecuteResponse>('/api/graph/cypher', request),
  });

// Link prediction
export const useLinkPrediction = () =>
  useMutation({
    mutationFn: (request: LinkPredictionRequest) =>
      post<LinkPredictionResponse>('/api/graph/algorithms/link-prediction', request),
  });

// Admin mutations
export const useCreateNode = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateNodeRequest) =>
      post<GraphNode>('/api/admin/graph/nodes', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.nodes() });
      queryClient.invalidateQueries({ queryKey: graphKeys.stats() });
    },
  });
};

export const useUpdateNode = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ nodeId, ...request }: UpdateNodeRequest & { nodeId: string }) =>
      put<GraphNode>(`/api/admin/graph/nodes/${nodeId}`, request),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: graphKeys.node(variables.nodeId) });
    },
  });
};

export const useDeleteNode = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (nodeId: string) => del<{ deleted: boolean }>(`/api/admin/graph/nodes/${nodeId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.nodes() });
      queryClient.invalidateQueries({ queryKey: graphKeys.stats() });
    },
  });
};

export const useCreateRelationship = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: CreateRelationshipRequest) =>
      post<GraphRelationship>('/api/admin/graph/relationships', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
};

export const useDeleteRelationship = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (relId: string) =>
      del<{ deleted: boolean }>(`/api/admin/graph/relationships/${relId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
};

// Bulk operations
export const useImportNodes = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ImportNodesRequest) =>
      post<ImportResponse>('/api/admin/graph/import/nodes', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
};

export const useImportRelationships = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (request: ImportRelationshipsRequest) =>
      post<ImportResponse>('/api/admin/graph/import/relationships', request),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
};

// Maintenance
export const useReindexDatabase = () =>
  useMutation({
    mutationFn: () => post<MaintenanceResponse>('/api/admin/graph/maintenance/reindex'),
  });

export const useDeleteOrphans = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => del<MaintenanceResponse>('/api/admin/graph/maintenance/orphans'),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: graphKeys.all });
    },
  });
};
