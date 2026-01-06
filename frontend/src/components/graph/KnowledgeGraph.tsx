import { useCallback, useEffect, useMemo, type MouseEvent } from 'react';

import '@xyflow/react/dist/style.css';

import {
  Background,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type NodeTypes,
  useEdgesState,
  useNodesState,
} from '@xyflow/react';

import { cn } from '@/lib/cn';

export interface KnowledgeGraphNodeData {
  label: string;
  description?: string;
  metadata?: Record<string, string>;
}

export type KnowledgeGraphNode = Node<KnowledgeGraphNodeData>;

export interface KnowledgeGraphEdgeData {
  label?: string;
  relation?: string;
}

export type KnowledgeGraphEdge = Edge<KnowledgeGraphEdgeData>;

interface KnowledgeGraphProps {
  nodes: KnowledgeGraphNode[];
  edges: KnowledgeGraphEdge[];
  onNodeClick?: (node: KnowledgeGraphNode) => void;
}

interface BaseGraphNodeProps {
  data: KnowledgeGraphNodeData;
  variant: 'entity' | 'concept';
}

const variantStyles = {
  entity: {
    container: 'rounded-full border-blue-500 bg-blue-50 text-blue-700',
    handle: '!bg-blue-500',
    description: 'text-blue-600',
  },
  concept: {
    container: 'rounded-xl border-emerald-500 bg-emerald-50 text-emerald-700',
    handle: '!bg-emerald-500',
    description: 'text-emerald-600',
  },
};

const BaseGraphNode = ({ data, variant }: BaseGraphNodeProps) => {
  const styles = variantStyles[variant];
  const positions = [Position.Top, Position.Right, Position.Left, Position.Bottom] as const;

  return (
    <div
      className={cn(
        'relative flex h-28 w-28 flex-col items-center justify-center gap-1 border-2 px-3 text-center text-sm font-semibold shadow-lg',
        variant === 'concept' && 'w-32 px-4',
        styles.container
      )}
    >
      {positions.map((position) => (
        <Handle
          key={position}
          type={position === Position.Top || position === Position.Left ? 'target' : 'source'}
          position={position}
          className={styles.handle}
          isConnectable={false}
        />
      ))}
      <span className="text-base">{data.label}</span>
      {data.description && (
        <span className={cn('text-xs font-normal', styles.description)}>{data.description}</span>
      )}
    </div>
  );
};

const EntityNode = ({ data }: NodeProps<KnowledgeGraphNodeData>) => (
  <BaseGraphNode data={data} variant="entity" />
);

const ConceptNode = ({ data }: NodeProps<KnowledgeGraphNodeData>) => (
  <BaseGraphNode data={data} variant="concept" />
);

const nodeTypes: NodeTypes = {
  entity: EntityNode,
  concept: ConceptNode,
};

export const KnowledgeGraph = ({ nodes, edges, onNodeClick }: KnowledgeGraphProps) => {
  const enhancedEdges = useMemo(
    () =>
      edges.map((edge) => ({
        ...edge,
        label: edge.label ?? edge.data?.label ?? edge.data?.relation,
      })),
    [edges]
  );

  const [graphNodes, setGraphNodes, onNodesChange] = useNodesState(nodes);
  const [graphEdges, setGraphEdges, onEdgesChange] = useEdgesState(enhancedEdges);

  useEffect(() => {
    setGraphNodes(nodes);
  }, [nodes, setGraphNodes]);

  useEffect(() => {
    setGraphEdges(enhancedEdges);
  }, [enhancedEdges, setGraphEdges]);

  const defaultEdgeOptions = useMemo(
    () => ({
      type: 'smoothstep',
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 20,
        height: 20,
        color: '#0f172a',
      },
      style: { stroke: '#0f172a', strokeWidth: 1.4 },
      labelStyle: { fill: '#0f172a', fontWeight: 600 },
      labelBgStyle: { fill: '#ffffff', fillOpacity: 0.85, stroke: '#cbd5f5', strokeWidth: 0.5 },
    }),
    []
  );

  const handleNodeClick = useCallback(
    (_: MouseEvent, node: Node) => {
      onNodeClick?.(node as KnowledgeGraphNode);
    },
    [onNodeClick]
  );

  return (
    <div className="h-full w-full rounded-2xl border border-slate-200 bg-white">
      <ReactFlow
        fitView
        nodes={graphNodes}
        edges={graphEdges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        minZoom={0.3}
        maxZoom={1.75}
        onNodeClick={handleNodeClick}
        proOptions={{ hideAttribution: true }}
        panOnDrag
        panOnScroll
        zoomOnScroll
        zoomOnPinch
        elementsSelectable
      >
        <Background color="#e2e8f0" gap={20} />
        <MiniMap
          nodeStrokeColor={(node) => (node.type === 'entity' ? '#2563eb' : '#059669')}
          nodeColor={(node) => (node.type === 'entity' ? '#bfdbfe' : '#bbf7d0')}
          pannable
          zoomable
        />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export default KnowledgeGraph;
