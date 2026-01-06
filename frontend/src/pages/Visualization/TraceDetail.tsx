import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Info, ShieldCheck } from 'lucide-react';

import { ReasoningTrace } from '@/components/graph';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { useVisualizationEvidence, useVisualizationTrace } from '@/hooks/useApi';

const TraceDetail = () => {
  const { traceId } = useParams<{ traceId: string }>();
  const navigate = useNavigate();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const traceQuery = useVisualizationTrace(traceId);
  const evidenceQuery = useVisualizationEvidence(selectedNodeId ?? undefined);

  const traceNodes = useMemo(() => {
    if (!traceQuery.data) return [];
    return traceQuery.data.nodes.map((node) => ({
      id: node.id,
      type: (node.metadata?.node_type as string) ?? node.type,
      data: {
        title: node.label,
        detail: typeof node.metadata?.detail === 'string' ? node.metadata.detail : undefined,
        confidence: typeof node.confidence === 'number' ? node.confidence : undefined,
        isOnCriticalPath: Boolean(node.metadata?.critical),
      },
      position: { x: 0, y: 0 },
    }));
  }, [traceQuery.data]);

  const traceEdges = useMemo(() => {
    if (!traceQuery.data) return [];
    return traceQuery.data.links.map((edge) => ({
      id: `${edge.source}-${edge.target}`,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      data: {
        label: edge.label,
        isOnCriticalPath: Boolean(
          traceQuery.data?.nodes.some((node) => node.id === edge.source && node.metadata?.critical)
        ),
      },
    }));
  }, [traceQuery.data]);

  const selectedNode = evidenceQuery.data;

  const renderGraph = () => {
    if (traceQuery.isLoading) {
      return (
        <div className="flex h-96 flex-col items-center justify-center gap-3 text-slate-500">
          <Spinner label="加载推理轨迹" />
          <p className="text-sm">轨迹渲染中，请稍候。</p>
        </div>
      );
    }
    if (traceQuery.isError) {
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50/80 p-4 text-sm text-red-600">
          {(traceQuery.error as Error)?.message || '加载失败，请稍后重试'}
        </div>
      );
    }
    if (!traceQuery.data) {
      return <p className="text-sm text-slate-500">暂无轨迹数据。</p>;
    }
    return (
      <ReasoningTrace
        nodes={traceNodes}
        edges={traceEdges}
        direction="LR"
        onNodeClick={(node) => setSelectedNodeId(node.id)}
      />
    );
  };

  return (
    <section className="grid gap-6 p-6 lg:grid-cols-[minmax(0,1fr)_320px]">
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Trace Detail</p>
            <h1 className="text-2xl font-semibold text-slate-900">推理轨迹</h1>
            <p className="mt-1 text-sm text-slate-600">Trace ID：{traceId}</p>
          </div>
          <div className="flex gap-2">
            <Button type="button" variant="outline" className="gap-2" onClick={() => navigate(-1)}>
              <ArrowLeft className="h-4 w-4" /> 返回
            </Button>
            <Button type="button" className="gap-2" onClick={() => navigate('/visualization')}>
              <ShieldCheck className="h-4 w-4" /> 验证报告
            </Button>
          </div>
        </div>

        <Card className="border-slate-100 shadow-none">
          <CardHeader>
            <CardTitle>推理图谱</CardTitle>
            <CardDescription>可视化 ReAct 节点与边，支持节点详情查看。</CardDescription>
          </CardHeader>
          <CardContent>{renderGraph()}</CardContent>
        </Card>
      </div>

      <aside className="space-y-4">
        <Card className="border-slate-100 shadow-none">
          <CardHeader>
            <CardTitle>节点详情</CardTitle>
            <CardDescription>选择图中节点查看上下文。</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="输入节点 ID，如 thought-1"
              value={selectedNodeId ?? ''}
              onChange={(event) => setSelectedNodeId(event.target.value)}
            />
            {selectedNodeId && evidenceQuery.isLoading ? (
              <div className="flex items-center gap-2 text-sm text-slate-500">
                <Spinner className="h-4 w-4" />
                拉取节点详情中...
              </div>
            ) : null}
            {selectedNode ? (
              <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
                <p className="text-xs uppercase tracking-wide text-slate-500">{selectedNode.type}</p>
                <p className="mt-1 text-base font-semibold text-slate-900">{selectedNode.label}</p>
                {typeof selectedNode.confidence === 'number' ? (
                  <p className="mt-2 text-xs text-slate-500">
                    置信度：{Math.round(selectedNode.confidence * 100)}%
                  </p>
                ) : null}
                {selectedNode.metadata ? (
                  <pre className="mt-3 max-h-48 overflow-y-auto rounded-xl bg-white p-3 text-xs text-slate-700">
                    {JSON.stringify(selectedNode.metadata, null, 2)}
                  </pre>
                ) : (
                  <p className="mt-3 text-xs text-slate-500">无更多元数据。</p>
                )}
              </div>
            ) : (
              <div className="flex flex-col items-center gap-2 rounded-2xl border border-dashed border-slate-200 p-4 text-sm text-slate-500">
                <Info className="h-5 w-5" />
                <p>点击节点或输入 ID 查看节点详情。</p>
              </div>
            )}
          </CardContent>
        </Card>
      </aside>
    </section>
  );
};

export default TraceDetail;
