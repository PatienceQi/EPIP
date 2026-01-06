/**
 * Graph API TypeScript type definitions
 */

export interface GraphNode {
  id: string;
  labels: string[];
  properties: Record<string, unknown>;
}

export interface GraphRelationship {
  id: string;
  type: string;
  start_node_id: string;
  end_node_id: string;
  properties: Record<string, unknown>;
}

export interface GraphData {
  nodes: GraphNode[];
  relationships: GraphRelationship[];
}

export interface GraphStats {
  node_count: number;
  relationship_count: number;
  label_counts: Record<string, number>;
  relationship_type_counts: Record<string, number>;
}

export interface NodesListResponse {
  nodes: GraphNode[];
  total: number;
  limit: number;
  offset: number;
}

export interface CreateNodeRequest {
  labels: string[];
  properties: Record<string, unknown>;
}

export interface UpdateNodeRequest {
  properties: Record<string, unknown>;
}

export interface CreateRelationshipRequest {
  start_node_id: string;
  end_node_id: string;
  type: string;
  properties?: Record<string, unknown>;
}

export interface CypherExecuteRequest {
  query: string;
  parameters?: Record<string, unknown>;
}

export interface CypherExecuteResponse {
  success: boolean;
  data: Record<string, unknown>[];
  columns: string[];
  execution_time_ms: number;
  is_write_query: boolean;
}

export interface ExpandNodeRequest {
  depth?: number;
}

export interface SearchNodesRequest {
  query: string;
  label?: string;
  limit?: number;
}

export interface ImportNodesRequest {
  nodes: CreateNodeRequest[];
}

export interface ImportRelationshipsRequest {
  relationships: CreateRelationshipRequest[];
}

export interface ImportResponse {
  created: number;
  failed: number;
  errors: string[];
}

export type ExportFormat = 'json' | 'csv';

export interface ExportRequest {
  format?: ExportFormat;
  label?: string;
  include_relationships?: boolean;
  limit?: number;
}

export type LinkPredictionAlgorithm = 'common_neighbors' | 'adamic_adar' | 'preferential_attachment';

export interface LinkPredictionRequest {
  node_id: string;
  algorithm?: LinkPredictionAlgorithm;
  limit?: number;
}

export interface PredictedLink {
  target_node: GraphNode;
  score: number;
  algorithm: string;
}

export interface LinkPredictionResponse {
  source_node_id: string;
  predictions: PredictedLink[];
}

export interface MaintenanceResponse {
  operation: string;
  success: boolean;
  affected_count: number;
  message: string;
}

export interface GraphHealthResponse {
  status: 'healthy' | 'unhealthy';
  connected: boolean;
  stats?: {
    node_count: number;
    relationship_count: number;
  };
}

// Flow graph node for React Flow
export interface FlowNode {
  id: string;
  type: 'graphNode';
  position: { x: number; y: number };
  data: {
    label: string;
    labels: string[];
    properties: Record<string, unknown>;
    isSelected?: boolean;
  };
}

// Flow graph edge for React Flow
export interface FlowEdge {
  id: string;
  source: string;
  target: string;
  type?: string;
  label?: string;
  data?: {
    relationshipType: string;
    properties: Record<string, unknown>;
  };
}
