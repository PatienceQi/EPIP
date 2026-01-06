export interface QueryRequest {
  query: string;
  source?: string;
}

export interface QueryResponse {
  answer: string;
  trace_id?: string;
  sources?: string[];
  confidence?: number;
  verification_report_url?: string;
  metadata?: Record<string, unknown>;
}

export type TenantStatus = 'ACTIVE' | 'SUSPENDED' | 'INACTIVE';

export interface Tenant {
  tenant_id: string;
  name: string;
  status: TenantStatus;
  config: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface CacheStats {
  hits: number;
  misses: number;
  hit_rate: number;
  size: number;
  memory_usage?: number;
}

export interface CacheClearResponse {
  pattern: string;
  cleared: number;
}

export interface ServiceStatus {
  neo4j: 'up' | 'down';
  redis: 'up' | 'down';
}

export interface HealthResponse {
  status: 'healthy' | 'unhealthy';
  services: ServiceStatus;
}

export interface VisualizationNode {
  id: string;
  label: string;
  type: string;
  confidence?: number;
  color?: string;
  size?: number;
  metadata?: Record<string, unknown>;
}

export interface VisualizationLink {
  source: string;
  target: string;
  label?: string;
  weight?: number;
  color?: string;
}

export interface VisualizationStats {
  nodes: number;
  edges: number;
  [key: string]: number;
}

export interface VisualizationData {
  layout?: string;
  nodes: VisualizationNode[];
  links: VisualizationLink[];
  stats?: VisualizationStats;
}

export interface VisualizationNodeContext {
  node_id: string;
  label: string;
  type: string;
  confidence?: number;
  metadata?: Record<string, unknown>;
}

export interface VisualizationExportPayload {
  graph: VisualizationData;
  format: 'json' | 'svg' | 'markdown';
  metadata?: Record<string, unknown>;
}

export interface VisualizationExportResponse {
  format: 'json' | 'svg' | 'markdown';
  content: VisualizationData | string;
}
