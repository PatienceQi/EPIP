import { useCallback, useEffect, useMemo, type MouseEvent } from 'react';

import '@xyflow/react/dist/style.css';

import { graphlib, layout as dagreLayout } from '@dagrejs/dagre';
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

type ReasoningNodeType = 'question' | 'thought' | 'action' | 'conclusion';
type LayoutDirection = 'TB' | 'LR';

export interface ReasoningNodeData {
  title: string;
  detail?: string;
  confidence?: number;
  isOnCriticalPath?: boolean;
}

export type ReasoningTraceNode = Node<ReasoningNodeData>;

export interface ReasoningEdgeData {
  label?: string;
  isOnCriticalPath?: boolean;
}

export type ReasoningTraceEdge = Edge<ReasoningEdgeData>;

interface ReasoningTraceProps {
  nodes: ReasoningTraceNode[];
  edges: ReasoningTraceEdge[];
  direction?: LayoutDirection;
  onNodeClick?: (node: ReasoningTraceNode) => void;
}

const NODE_WIDTH = 260;
const NODE_HEIGHT = 120;

const nodePalette: Record<ReasoningNodeType, { rgb: string; border: string; label: string }> = {
  question: { rgb: '59,130,246', border: '#1d4ed8', label: 'Question' },
  thought: { rgb: '250,204,21', border: '#ca8a04', label: 'Thought' },
  action: { rgb: '34,197,94', border: '#15803d', label: 'Action' },
  conclusion: { rgb: '168,85,247', border: '#7c3aed', label: 'Conclusion' },
};

const clampConfidence = (value?: number): number => {
  if (value == null || Number.isNaN(value)) return 0.5;
  return Math.min(1, Math.max(0, value));
};

const getNodeVisualStyle = (type: ReasoningNodeType, confidence?: number) => {
  const palette = nodePalette[type];
  const normalized = clampConfidence(confidence);
  const alpha = 0.35 + normalized * 0.5;

  return {
    backgroundColor: `rgba(${palette.rgb}, ${alpha.toFixed(2)})`,
    borderColor: palette.border,
  };
};

const ReasoningNodeCard = ({ data, type }: NodeProps<ReasoningNodeData>) => {
  const nodeType = (type as ReasoningNodeType) ?? 'thought';
  const palette = nodePalette[nodeType];
  const visuals = getNodeVisualStyle(nodeType, data.confidence);
  const confidencePercent = Math.round(clampConfidence(data.confidence) * 100);

  return (
    <div
      style={visuals}
      className={cn(
        'relative min-w-[240px] rounded-2xl border-2 p-4 text-left text-sm text-slate-900 shadow-xl transition-all',
        data.isOnCriticalPath ? 'ring-2 ring-purple-400' : 'ring-0'
      )}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!h-2 !w-2 !bg-slate-700"
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!h-2 !w-2 !bg-slate-700"
        isConnectable={false}
      />
      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !bg-slate-700"
        isConnectable={false}
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !bg-slate-700"
        isConnectable={false}
      />
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
        {palette.label}
      </p>
      <p className="mt-1 text-lg font-semibold text-slate-900">{data.title}</p>
      {data.detail ? <p className="mt-2 text-sm text-slate-600">{data.detail}</p> : null}
      <div className="mt-3 flex items-center justify-between text-xs font-medium text-slate-700">
        <span>Confidence</span>
        <span>{confidencePercent}%</span>
      </div>
    </div>
  );
};

const reasoningNodeTypes: NodeTypes = {
  question: (props) => <ReasoningNodeCard {...props} />,
  thought: (props) => <ReasoningNodeCard {...props} />,
  action: (props) => <ReasoningNodeCard {...props} />,
  conclusion: (props) => <ReasoningNodeCard {...props} />,
};

const layoutReasoningTrace = (
  nodes: ReasoningTraceNode[],
  edges: ReasoningTraceEdge[],
  direction: LayoutDirection
) => {
  const dagreGraph = new graphlib.Graph();
  dagreGraph.setGraph({ rankdir: direction, nodesep: 80, ranksep: 120, marginx: 30, marginy: 30 });
  dagreGraph.setDefaultEdgeLabel(() => ({}));

  nodes.forEach((node) => {
    dagreGraph.setNode(node.id, {
      width: node.width ?? NODE_WIDTH,
      height: node.height ?? NODE_HEIGHT,
    });
  });

  edges.forEach((edge) => {
    dagreGraph.setEdge(edge.source, edge.target);
  });

  dagreLayout(dagreGraph);

  const isHorizontal = direction === 'LR';

  const layoutedNodes = nodes.map((node) => {
    const { x, y } = dagreGraph.node(node.id);
    const width = node.width ?? NODE_WIDTH;
    const height = node.height ?? NODE_HEIGHT;

    return {
      ...node,
      position: { x: x - width / 2, y: y - height / 2 },
      sourcePosition: isHorizontal ? Position.Right : Position.Bottom,
      targetPosition: isHorizontal ? Position.Left : Position.Top,
      style: {
        ...(node.style ?? {}),
        width,
        height,
      },
    };
  });

  const layoutedEdges = edges.map((edge) => {
    const isCritical = edge.data?.isOnCriticalPath ?? false;
    const markerColor = isCritical ? '#7c3aed' : '#94a3b8';

    return {
      ...edge,
      type: edge.type ?? 'smoothstep',
      label: edge.label ?? edge.data?.label,
      markerEnd: {
        type: MarkerType.ArrowClosed,
        width: 18,
        height: 18,
        color: markerColor,
      },
      style: {
        stroke: markerColor,
        strokeWidth: isCritical ? 3 : 1.6,
        ...(edge.style ?? {}),
      },
      labelStyle: {
        fill: '#0f172a',
        fontWeight: 600,
        ...(edge.labelStyle ?? {}),
      },
      labelBgStyle: {
        fill: '#ffffff',
        fillOpacity: 0.85,
        stroke: isCritical ? '#7c3aed' : '#cbd5f5',
        ...(edge.labelBgStyle ?? {}),
      },
    };
  });

  return { nodes: layoutedNodes, edges: layoutedEdges };
};

export const ReasoningTrace = ({
  nodes,
  edges,
  direction = 'TB',
  onNodeClick,
}: ReasoningTraceProps): JSX.Element => {
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => layoutReasoningTrace(nodes, edges, direction),
    [nodes, edges, direction]
  );

  const [traceNodes, setTraceNodes, onNodesChange] = useNodesState(layoutedNodes);
  const [traceEdges, setTraceEdges, onEdgesChange] = useEdgesState(layoutedEdges);

  useEffect(() => {
    setTraceNodes(layoutedNodes);
  }, [layoutedNodes, setTraceNodes]);

  useEffect(() => {
    setTraceEdges(layoutedEdges);
  }, [layoutedEdges, setTraceEdges]);

  const handleNodeClick = useCallback(
    (_: MouseEvent, node: Node) => {
      if (onNodeClick) {
        onNodeClick(node as ReasoningTraceNode);
      }
    },
    [onNodeClick]
  );

  return (
    <div className="h-full w-full rounded-2xl border border-slate-200 bg-white">
      <ReactFlow
        fitView
        nodes={traceNodes}
        edges={traceEdges}
        nodeTypes={reasoningNodeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick ? handleNodeClick : undefined}
        minZoom={0.3}
        maxZoom={1.5}
        panOnDrag
        panOnScroll
        zoomOnScroll
        proOptions={{ hideAttribution: true }}
      >
        <Background gap={20} color="#e2e8f0" />
        <MiniMap
          nodeColor={(node) => {
            const palette = nodePalette[(node.type as ReasoningNodeType) ?? 'thought'];
            return `rgba(${palette.rgb}, 0.7)`;
          }}
          nodeStrokeColor={(node) => nodePalette[(node.type as ReasoningNodeType) ?? 'thought'].border}
        />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
};

export default ReasoningTrace;
