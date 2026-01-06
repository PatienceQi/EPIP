import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Edge,
  Node,
  NodeTypes,
  Handle,
  Position,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import {
  Database,
  Expand,
  Filter,
  Plus,
  RefreshCw,
  Search,
  Settings,
  Trash2,
  X,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Spinner } from '@/components/ui/spinner';
import {
  useGraphNodes,
  useGraphLabels,
  useGraphStats,
  useExpandNode,
  useSearchNodes,
  useCreateNode,
  useUpdateNode,
  useDeleteNode,
} from '@/hooks/useGraph';
import { useTenantStore } from '@/stores/tenantStore';
import { cn } from '@/lib/cn';
import type { GraphNode as GraphNodeType, FlowNode, FlowEdge } from '@/types/graph';

const COLORS = [
  '#6366f1', '#8b5cf6', '#ec4899', '#f43f5e', '#f97316',
  '#eab308', '#22c55e', '#14b8a6', '#06b6d4', '#3b82f6',
];

const getLabelColor = (label: string): string => {
  const hash = label.split('').reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return COLORS[hash % COLORS.length];
};

// Custom Node Component
const GraphNodeComponent = ({ data, selected }: { data: FlowNode['data']; selected: boolean }) => {
  const primaryLabel = data.labels[0] ?? 'Node';
  const color = getLabelColor(primaryLabel);

  return (
    <>
      <Handle type="target" position={Position.Top} style={{ visibility: 'hidden' }} />
      <div
        className={cn(
          'rounded-lg border-2 bg-white px-3 py-2 shadow-md transition-all',
          selected ? 'ring-2 ring-indigo-500 ring-offset-2' : ''
        )}
        style={{ borderColor: color }}
      >
        <div className="flex items-center gap-2">
          <div
            className="h-3 w-3 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="text-sm font-medium text-slate-900">
            {data.label || primaryLabel}
          </span>
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {data.labels.slice(0, 3).map((label) => (
            <Badge
              key={label}
              variant="secondary"
              className="text-xs"
              style={{ backgroundColor: `${getLabelColor(label)}20`, color: getLabelColor(label) }}
            >
              {label}
            </Badge>
          ))}
        </div>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ visibility: 'hidden' }} />
    </>
  );
};

const nodeTypes: NodeTypes = {
  graphNode: GraphNodeComponent,
};

interface NodeDetailPanelProps {
  node: GraphNodeType | null;
  isAdmin: boolean;
  onClose: () => void;
  onExpand: (nodeId: string) => void;
  onEdit: (node: GraphNodeType) => void;
  onDelete: (nodeId: string) => void;
}

const NodeDetailPanel = ({
  node,
  isAdmin,
  onClose,
  onExpand,
  onEdit,
  onDelete,
}: NodeDetailPanelProps) => {
  if (!node) return null;

  return (
    <div className="absolute right-4 top-4 z-10 w-80 rounded-xl border border-slate-200 bg-white shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-100 p-4">
        <h3 className="font-semibold text-slate-900">节点详情</h3>
        <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
          <X className="h-4 w-4" />
        </button>
      </div>
      <div className="max-h-[60vh] overflow-y-auto p-4">
        <div className="space-y-4">
          <div>
            <p className="text-xs font-medium uppercase text-slate-500">ID</p>
            <p className="mt-1 break-all text-sm text-slate-700">{node.id}</p>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-slate-500">标签</p>
            <div className="mt-1 flex flex-wrap gap-1">
              {node.labels.map((label) => (
                <Badge
                  key={label}
                  variant="secondary"
                  style={{
                    backgroundColor: `${getLabelColor(label)}20`,
                    color: getLabelColor(label),
                  }}
                >
                  {label}
                </Badge>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium uppercase text-slate-500">属性</p>
            <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-slate-50 p-2 text-xs text-slate-700">
              {JSON.stringify(node.properties, null, 2)}
            </pre>
          </div>
        </div>
      </div>
      <div className="flex gap-2 border-t border-slate-100 p-4">
        <Button
          size="sm"
          variant="outline"
          className="flex-1 gap-1"
          onClick={() => onExpand(node.id)}
        >
          <Expand className="h-3 w-3" />
          展开
        </Button>
        {isAdmin && (
          <>
            <Button
              size="sm"
              variant="outline"
              className="flex-1 gap-1"
              onClick={() => onEdit(node)}
            >
              <Settings className="h-3 w-3" />
              编辑
            </Button>
            <Button
              size="sm"
              variant="outline"
              className="flex-1 gap-1 text-red-600 hover:bg-red-50"
              onClick={() => onDelete(node.id)}
            >
              <Trash2 className="h-3 w-3" />
              删除
            </Button>
          </>
        )}
      </div>
    </div>
  );
};

interface CreateNodeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCreate: (labels: string[], properties: Record<string, unknown>) => void;
  availableLabels: string[];
}

const CreateNodeModal = ({ isOpen, onClose, onCreate, availableLabels }: CreateNodeModalProps) => {
  const [labels, setLabels] = useState<string[]>([]);
  const [newLabel, setNewLabel] = useState('');
  const [propertiesJson, setPropertiesJson] = useState('{}');
  const [error, setError] = useState('');

  const handleSubmit = () => {
    if (labels.length === 0) {
      setError('请至少选择一个标签');
      return;
    }
    try {
      const properties = JSON.parse(propertiesJson);
      onCreate(labels, properties);
      onClose();
      setLabels([]);
      setPropertiesJson('{}');
    } catch {
      setError('属性 JSON 格式无效');
    }
  };

  const addLabel = (label: string) => {
    if (label && !labels.includes(label)) {
      setLabels([...labels, label]);
      setNewLabel('');
    }
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title="创建节点">
      <div className="space-y-4">
        <div>
          <label className="text-sm font-medium text-slate-700">标签</label>
          <div className="mt-1 flex flex-wrap gap-1">
            {labels.map((label) => (
              <Badge
                key={label}
                variant="secondary"
                className="cursor-pointer"
                onClick={() => setLabels(labels.filter((l) => l !== label))}
              >
                {label} ×
              </Badge>
            ))}
          </div>
          <div className="mt-2 flex gap-2">
            <Input
              placeholder="新标签"
              value={newLabel}
              onChange={(e) => setNewLabel(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addLabel(newLabel)}
            />
            <Button size="sm" onClick={() => addLabel(newLabel)}>
              添加
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            {availableLabels
              .filter((l) => !labels.includes(l))
              .slice(0, 5)
              .map((label) => (
                <Badge
                  key={label}
                  variant="outline"
                  className="cursor-pointer hover:bg-slate-100"
                  onClick={() => addLabel(label)}
                >
                  + {label}
                </Badge>
              ))}
          </div>
        </div>
        <div>
          <label className="text-sm font-medium text-slate-700">属性 (JSON)</label>
          <textarea
            className="mt-1 w-full rounded-lg border border-slate-200 p-2 font-mono text-sm"
            rows={5}
            value={propertiesJson}
            onChange={(e) => setPropertiesJson(e.target.value)}
          />
        </div>
        {error && <p className="text-sm text-red-500">{error}</p>}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            取消
          </Button>
          <Button onClick={handleSubmit}>创建</Button>
        </div>
      </div>
    </Modal>
  );
};

const GraphExplorer = () => {
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNodeType | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [labelFilter, setLabelFilter] = useState<string | null>(null);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [expandedNodeIds, setExpandedNodeIds] = useState<Set<string>>(new Set());

  const currentTenant = useTenantStore((state) =>
    state.tenants.find((t) => t.tenant_id === state.currentTenantId)
  );
  const isAdmin = currentTenant?.config?.role === 'admin';

  const { data: nodesData, isLoading, refetch } = useGraphNodes({
    label: labelFilter ?? undefined,
    limit: 50,
  });
  const { data: labelsData } = useGraphLabels();
  const { data: statsData } = useGraphStats();
  const searchMutation = useSearchNodes();
  const createNodeMutation = useCreateNode();
  const deleteNodeMutation = useDeleteNode();

  // Convert graph nodes to React Flow nodes
  const convertToFlowNodes = useCallback(
    (graphNodes: GraphNodeType[], existingNodes: Node[]): Node[] => {
      const existingPositions = new Map(existingNodes.map((n) => [n.id, n.position]));

      return graphNodes.map((node, index) => {
        const existing = existingPositions.get(node.id);
        const angle = (index / graphNodes.length) * 2 * Math.PI;
        const radius = 200;

        return {
          id: node.id,
          type: 'graphNode',
          position: existing ?? {
            x: 400 + Math.cos(angle) * radius,
            y: 300 + Math.sin(angle) * radius,
          },
          data: {
            label: (node.properties.name as string) ?? node.labels[0] ?? 'Node',
            labels: node.labels,
            properties: node.properties,
          },
        };
      });
    },
    []
  );

  // Update nodes when data changes
  useEffect(() => {
    if (nodesData?.nodes) {
      setNodes((prev) => convertToFlowNodes(nodesData.nodes, prev));
    }
  }, [nodesData, convertToFlowNodes, setNodes]);

  const handleNodeClick = useCallback(
    (_: React.MouseEvent, node: Node) => {
      const graphNode = nodesData?.nodes.find((n) => n.id === node.id);
      if (graphNode) {
        setSelectedNode(graphNode);
      }
    },
    [nodesData]
  );

  const handleExpandNode = useCallback(
    async (nodeId: string) => {
      if (expandedNodeIds.has(nodeId)) return;

      // Fetch expanded data - this is a simplified version
      // In a real implementation, you'd call the expand API
      setExpandedNodeIds((prev) => new Set([...prev, nodeId]));
    },
    [expandedNodeIds]
  );

  const handleSearch = useCallback(() => {
    if (searchQuery.trim()) {
      searchMutation.mutate(
        { query: searchQuery, limit: 20 },
        {
          onSuccess: (results) => {
            setNodes((prev) => convertToFlowNodes(results, prev));
          },
        }
      );
    }
  }, [searchQuery, searchMutation, convertToFlowNodes, setNodes]);

  const handleCreateNode = useCallback(
    (labels: string[], properties: Record<string, unknown>) => {
      createNodeMutation.mutate(
        { labels, properties },
        {
          onSuccess: () => {
            refetch();
          },
        }
      );
    },
    [createNodeMutation, refetch]
  );

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      if (confirm('确定要删除此节点吗？这将同时删除相关的所有关系。')) {
        deleteNodeMutation.mutate(nodeId, {
          onSuccess: () => {
            setSelectedNode(null);
            setNodes((prev) => prev.filter((n) => n.id !== nodeId));
            refetch();
          },
        });
      }
    },
    [deleteNodeMutation, refetch, setNodes]
  );

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  return (
    <section className="flex h-[calc(100vh-4rem)] flex-col p-6">
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Graph Explorer
          </p>
          <h1 className="text-2xl font-semibold text-slate-900">图数据库浏览器</h1>
          <p className="mt-1 text-sm text-slate-600">
            可视化探索 Neo4j 图数据库中的节点和关系
          </p>
        </div>
        <div className="flex items-center gap-2">
          {statsData && (
            <div className="flex gap-4 rounded-lg bg-slate-50 px-4 py-2 text-sm">
              <span className="text-slate-600">
                节点: <strong className="text-slate-900">{statsData.node_count}</strong>
              </span>
              <span className="text-slate-600">
                关系: <strong className="text-slate-900">{statsData.relationship_count}</strong>
              </span>
            </div>
          )}
          <Button variant="outline" size="sm" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
          </Button>
          {isAdmin && (
            <Button size="sm" onClick={() => setShowCreateModal(true)}>
              <Plus className="mr-1 h-4 w-4" />
              创建节点
            </Button>
          )}
        </div>
      </header>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <Input
            placeholder="搜索节点..."
            className="pl-9"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          />
        </div>
        <div className="flex items-center gap-2">
          <Filter className="h-4 w-4 text-slate-400" />
          <select
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={labelFilter ?? ''}
            onChange={(e) => setLabelFilter(e.target.value || null)}
          >
            <option value="">所有标签</option>
            {labelsData?.map((label) => (
              <option key={label} value={label}>
                {label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <Card className="flex-1 border-slate-100 shadow-none">
        <CardContent className="relative h-full p-0">
          {isLoading ? (
            <div className="flex h-full items-center justify-center">
              <Spinner label="加载图数据..." />
            </div>
          ) : (
            <ReactFlow
              nodes={nodes}
              edges={edges}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={handleNodeClick}
              nodeTypes={nodeTypes}
              fitView
              className="bg-slate-50"
            >
              <Background />
              <Controls />
              <MiniMap
                nodeColor={(node) => {
                  const label = (node.data as FlowNode['data']).labels[0];
                  return label ? getLabelColor(label) : '#94a3b8';
                }}
              />
            </ReactFlow>
          )}

          <NodeDetailPanel
            node={selectedNode}
            isAdmin={isAdmin}
            onClose={() => setSelectedNode(null)}
            onExpand={handleExpandNode}
            onEdit={() => {}}
            onDelete={handleDeleteNode}
          />
        </CardContent>
      </Card>

      <CreateNodeModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreate={handleCreateNode}
        availableLabels={labelsData ?? []}
      />
    </section>
  );
};

export default GraphExplorer;
