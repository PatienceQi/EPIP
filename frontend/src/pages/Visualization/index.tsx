import { useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ChevronDown, Download, GitBranch, Network, Search, ShieldCheck } from 'lucide-react';

import { KnowledgeGraph, ReasoningTrace } from '@/components/graph';
import type { KnowledgeGraphEdge, KnowledgeGraphNode } from '@/components/graph/KnowledgeGraph';
import type { ReasoningTraceEdge, ReasoningTraceNode } from '@/components/graph/ReasoningTrace';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/cn';
import { useExportVisualization, useVisualizationTrace, useVisualizationVerification } from '@/hooks/useApi';
import type { VisualizationNode } from '@/types/api';

type TabKey = 'graph' | 'trace' | 'verification';

const TABS: Array<{ key: TabKey; label: string; description: string }> = [
  { key: 'graph', label: '知识图谱', description: '探索推理节点、实体与关系' },
  { key: 'trace', label: '推理轨迹', description: '预览 ReAct 执行路径与关键节点' },
  { key: 'verification', label: '验证报告', description: '查看事实检验节点与证据' },
];

const EXPORT_OPTIONS: Array<{ label: string; value: 'json' | 'svg' | 'markdown' }> = [
  { label: '导出 JSON', value: 'json' },
  { label: '导出 SVG', value: 'svg' },
  { label: '导出 Markdown', value: 'markdown' },
];

const mapNodeType = (node: VisualizationNode): 'entity' | 'concept' => {
  const type = (node.metadata?.node_type as string) ?? node.type ?? '';
  if (type.toLowerCase().includes('concept') || type.toLowerCase().includes('fact')) {
    return 'concept';
  }
  return 'entity';
};

const Visualization = () => {
  const [activeTab, setActiveTab] = useState<TabKey>('graph');
  const [traceIdInput, setTraceIdInput] = useState('');
  const [answerIdInput, setAnswerIdInput] = useState('');
  const [searchValue, setSearchValue] = useState('');
  const [focusedNodeId, setFocusedNodeId] = useState<string | null>(null);
  const [exportMenuOpen, setExportMenuOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement | null>(null);

  const traceQuery = useVisualizationTrace(traceIdInput || undefined);
  const verificationQuery = useVisualizationVerification(answerIdInput || undefined);
  const exportMutation = useExportVisualization();

  const traceNodesRaw = traceQuery.data?.nodes ?? [];
  const traceLinksRaw = traceQuery.data?.links ?? [];

  useEffect(() => {
    const handleClick = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setExportMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => {
      document.removeEventListener('mousedown', handleClick);
    };
  }, []);

  useEffect(() => {
    setSearchValue('');
    setFocusedNodeId(null);
  }, [traceIdInput]);

  useEffect(() => {
    if (focusedNodeId && !traceNodesRaw.some((node) => node.id === focusedNodeId)) {
      setFocusedNodeId(null);
    }
  }, [traceNodesRaw, focusedNodeId]);

  const filteredNodes = useMemo<VisualizationNode[]>(() => {
    const keyword = searchValue.trim().toLowerCase();
    if (!keyword) {
      return traceNodesRaw;
    }
    return traceNodesRaw.filter((node) => {
      const labelMatch = node.label.toLowerCase().includes(keyword);
      const metadataMatch = JSON.stringify(node.metadata ?? {}).toLowerCase().includes(keyword);
      return labelMatch || metadataMatch;
    });
  }, [traceNodesRaw, searchValue]);

  const filteredNodeIds = useMemo(() => new Set(filteredNodes.map((node) => node.id)), [filteredNodes]);

  const filteredLinks = useMemo(
    () =>
      traceLinksRaw.filter(
        (edge) =>
          filteredNodeIds.has(String(edge.source)) && filteredNodeIds.has(String(edge.target))
      ),
    [filteredNodeIds, traceLinksRaw]
  );

  const knowledgeGraphNodes = useMemo<KnowledgeGraphNode[]>(() => {
    if (filteredNodes.length === 0) return [];
    const baseX = 380;
    const baseY = 260;
    const radius = 220;
    return filteredNodes.map((node, index) => {
      const progress = filteredNodes.length > 1 ? index / filteredNodes.length : 0;
      const angle = progress * Math.PI * 2;
      return {
        id: node.id,
        type: mapNodeType(node),
        data: {
          label: node.label,
          description:
            typeof node.metadata?.detail === 'string' ? node.metadata.detail : undefined,
          metadata: node.metadata as Record<string, string> | undefined,
        },
        position: {
          x: baseX + Math.cos(angle) * radius,
          y: baseY + Math.sin(angle) * radius,
        },
      };
    });
  }, [filteredNodes]);

  const knowledgeGraphEdges = useMemo<KnowledgeGraphEdge[]>(() => {
    if (filteredLinks.length === 0) return [];
    return filteredLinks.map((edge, index) => ({
      id: `${edge.source}-${edge.target}-${index}`,
      source: String(edge.source),
      target: String(edge.target),
      label: edge.label,
      data: { label: edge.label, relation: edge.label },
    }));
  }, [filteredLinks]);

  const criticalNodeIds = useMemo(
    () =>
      new Set(
        traceNodesRaw.filter((node) => node.metadata?.critical).map((node) => node.id)
      ),
    [traceNodesRaw]
  );

  const reasoningTraceNodes = useMemo<ReasoningTraceNode[]>(
    () =>
      traceNodesRaw.map((node) => ({
        id: node.id,
        type: (node.metadata?.node_type as string) ?? node.type ?? 'thought',
        data: {
          title: node.label,
          detail: typeof node.metadata?.detail === 'string' ? node.metadata.detail : undefined,
          confidence: typeof node.confidence === 'number' ? node.confidence : undefined,
          isOnCriticalPath: Boolean(node.metadata?.critical),
        },
        position: { x: 0, y: 0 },
      })),
    [traceNodesRaw]
  );

  const reasoningTraceEdges = useMemo<ReasoningTraceEdge[]>(
    () =>
      traceLinksRaw.map((edge, index) => ({
        id: `${edge.source}-${edge.target}-${index}`,
        source: String(edge.source),
        target: String(edge.target),
        label: edge.label,
        data: {
          label: edge.label,
          isOnCriticalPath:
            criticalNodeIds.has(String(edge.source)) || criticalNodeIds.has(String(edge.target)),
        },
      })),
    [criticalNodeIds, traceLinksRaw]
  );

  const focusedNode =
    focusedNodeId != null
      ? filteredNodes.find((node) => node.id === focusedNodeId) ?? null
      : null;

  const handleExport = (format: 'json' | 'svg' | 'markdown') => {
    const graphPayload = activeTab === 'verification' ? verificationQuery.data : traceQuery.data;
    if (!graphPayload) return;
    exportMutation.mutate(
      {
        graph: graphPayload,
        format,
        metadata: {
          generated_at: new Date().toISOString(),
          trace_id: traceIdInput || undefined,
          answer_id: answerIdInput || undefined,
          tab: activeTab,
        },
      },
      { onSuccess: () => setExportMenuOpen(false) }
    );
  };

  const renderGraphTab = () => {
    if (!traceIdInput) {
      return <p className="text-sm text-slate-500">请输入 Trace ID 以载入图谱。</p>;
    }
    if (traceQuery.isLoading) {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-500">
          <Spinner label="加载图谱" />
          <p className="text-sm">推理图谱拉取中，请稍候...</p>
        </div>
      );
    }
    if (traceQuery.isError) {
      return (
        <p className="text-sm text-red-500">
          {(traceQuery.error as Error)?.message || '拉取失败，请检查 Trace ID'}
        </p>
      );
    }
    if (!traceNodesRaw.length) {
      return <p className="text-sm text-slate-500">暂无图谱节点可展示。</p>;
    }
    return (
      <div className="space-y-6">
        <div className="flex flex-col gap-3 lg:flex-row">
          <div className="relative lg:w-72">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <Input
              placeholder="搜索节点标签或元数据"
              className="pl-9"
              value={searchValue}
              onChange={(event) => setSearchValue(event.target.value)}
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
            <p>节点匹配：{filteredNodes.length}</p>
            <p>关系匹配：{filteredLinks.length}</p>
          </div>
        </div>
        <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="h-[520px]">
            <KnowledgeGraph
              nodes={knowledgeGraphNodes}
              edges={knowledgeGraphEdges}
              onNodeClick={(node) => setFocusedNodeId(node.id)}
            />
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            {focusedNode ? (
              <>
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">
                  {focusedNode.type}
                </p>
                <p className="mt-1 text-base font-semibold text-slate-900">{focusedNode.label}</p>
                {typeof focusedNode.confidence === 'number' ? (
                  <p className="mt-2 text-xs text-slate-500">
                    置信度：{Math.round(focusedNode.confidence * 100)}%
                  </p>
                ) : null}
                <pre className="mt-3 max-h-56 overflow-y-auto rounded-xl bg-white p-3 text-xs text-slate-700">
                  {JSON.stringify(focusedNode.metadata ?? {}, null, 2)}
                </pre>
              </>
            ) : (
              <div className="flex h-full flex-col items-center justify-center gap-2 text-center text-slate-500">
                <Network className="h-5 w-5" />
                <p>点击图中节点以查看详情。</p>
              </div>
            )}
          </div>
        </div>
        <div className="grid gap-3 md:grid-cols-2">
          {filteredNodes.slice(0, 4).map((node) => (
            <Card key={node.id} className="border-slate-100 shadow-none">
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{node.label}</CardTitle>
                <CardDescription className="text-xs uppercase text-slate-400">
                  {node.type}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <pre className="max-h-36 overflow-y-auto rounded-xl bg-slate-900/90 p-3 text-xs text-slate-100">
                  {JSON.stringify(node.metadata ?? {}, null, 2)}
                </pre>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    );
  };

  const renderTraceTab = () => {
    if (!traceIdInput) {
      return <p className="text-sm text-slate-500">请输入 Trace ID 查看推理轨迹。</p>;
    }
    if (traceQuery.isLoading) {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-500">
          <Spinner label="加载推理轨迹" />
          <p className="text-sm">轨迹渲染中，请稍候...</p>
        </div>
      );
    }
    if (traceQuery.isError) {
      return (
        <p className="text-sm text-red-500">
          {(traceQuery.error as Error)?.message || '无法加载推理轨迹'}
        </p>
      );
    }
    if (!traceNodesRaw.length) {
      return <p className="text-sm text-slate-500">当前 Trace 未包含节点。</p>;
    }
    return (
      <div className="space-y-4">
        <div className="h-[540px]">
          <ReasoningTrace nodes={reasoningTraceNodes} edges={reasoningTraceEdges} direction="LR" />
        </div>
        <div className="flex flex-wrap items-center gap-3 text-sm text-slate-600">
          <Link
            to={`/visualization/trace/${traceIdInput}`}
            className="inline-flex items-center gap-2 rounded-full bg-slate-900 px-4 py-2 text-white"
          >
            <GitBranch className="h-4 w-4" />
            跳转到轨迹详情
          </Link>
          {traceQuery.data?.stats ? (
            <span>
              节点 {traceQuery.data.stats.nodes} · 边 {traceQuery.data.stats.edges}
            </span>
          ) : null}
        </div>
      </div>
    );
  };

  const renderVerificationTab = () => {
    if (!answerIdInput) {
      return <p className="text-sm text-slate-500">请输入 Answer ID 获取验证报告。</p>;
    }
    if (verificationQuery.isLoading) {
      return (
        <div className="flex h-64 flex-col items-center justify-center gap-3 text-slate-500">
          <Spinner label="加载验证报告" />
          <p className="text-sm">验证图谱拉取中，请稍候...</p>
        </div>
      );
    }
    if (verificationQuery.isError) {
      return (
        <p className="text-sm text-red-500">
          {(verificationQuery.error as Error)?.message || '无法加载验证报告'}
        </p>
      );
    }
    const data = verificationQuery.data;
    if (!data) {
      return <p className="text-sm text-slate-500">暂无验证报告。</p>;
    }
    const stats = data.stats ?? {
      nodes: data.nodes.length,
      edges: data.links.length,
    };
    return (
      <div className="space-y-5">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p className="text-xs uppercase tracking-wide text-slate-500">节点总数</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{stats.nodes}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p className="text-xs uppercase tracking-wide text-slate-500">边总数</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{stats.edges}</p>
          </div>
          <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-600">
            <p className="text-xs uppercase tracking-wide text-slate-500">Answer ID</p>
            <p className="mt-2 text-2xl font-semibold text-slate-900">{answerIdInput}</p>
          </div>
        </div>
        <div className="rounded-2xl border border-slate-100 bg-white p-4">
          <p className="text-sm font-semibold text-slate-700">节点采样</p>
          <ul className="mt-3 space-y-2 text-sm text-slate-600">
            {data.nodes.slice(0, 5).map((node) => (
              <li key={node.id} className="rounded-xl border border-slate-100 px-4 py-2">
                <p className="text-xs uppercase tracking-wide text-slate-400">{node.type}</p>
                <p className="text-sm font-semibold text-slate-900">{node.label}</p>
                {typeof node.confidence === 'number' ? (
                  <p className="text-xs text-slate-500">
                    置信度：{Math.round(node.confidence * 100)}%
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  };

  const renderContent = () => {
    if (activeTab === 'graph') return renderGraphTab();
    if (activeTab === 'trace') return renderTraceTab();
    return renderVerificationTab();
  };

  return (
    <section className="space-y-6 p-6">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            Visualization Center
          </p>
          <h1 className="text-2xl font-semibold text-slate-900">可视化面板</h1>
          <p className="mt-2 text-sm text-slate-600">切换标签查看图谱、推理轨迹与验证报告。</p>
        </div>
        <div className="flex flex-col gap-2 text-right">
          <div
            className="relative flex flex-wrap items-center justify-end gap-2"
            ref={dropdownRef}
          >
            <Button
              type="button"
              variant="outline"
              className="gap-2"
              onClick={() => setExportMenuOpen((value) => !value)}
            >
              <Download className="h-4 w-4" />
              导出
              <ChevronDown className="h-4 w-4" />
            </Button>
            {exportMenuOpen ? (
              <div className="absolute right-0 top-full z-10 mt-2 w-36 rounded-md border border-slate-200 bg-white shadow-lg">
                {EXPORT_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    className="w-full px-4 py-2 text-left text-sm text-slate-600 hover:bg-slate-50"
                    onClick={() => handleExport(option.value)}
                    disabled={exportMutation.isPending}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            ) : null}
          </div>
          {exportMutation.isError ? (
            <span className="text-xs text-red-500">
              {(exportMutation.error as Error)?.message || '导出失败'}
            </span>
          ) : null}
          {exportMutation.isSuccess ? (
            <span className="text-xs text-emerald-600">
              已生成 {exportMutation.data?.format?.toUpperCase()} 导出
            </span>
          ) : null}
        </div>
      </header>

      <div className="flex flex-wrap gap-2">
        {TABS.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'rounded-full px-4 py-2 text-sm font-medium transition',
              activeTab === tab.key
                ? 'bg-slate-900 text-white shadow'
                : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <Card className="border-slate-100 shadow-none">
        <CardHeader className="gap-2">
          <CardTitle className="flex items-center gap-2 text-lg">
            {activeTab === 'graph' && <Network className="h-5 w-5 text-indigo-500" />}
            {activeTab === 'trace' && <GitBranch className="h-5 w-5 text-indigo-500" />}
            {activeTab === 'verification' && <ShieldCheck className="h-5 w-5 text-emerald-500" />}
            {TABS.find((tab) => tab.key === activeTab)?.label}
          </CardTitle>
          <CardDescription>
            {TABS.find((tab) => tab.key === activeTab)?.description}
          </CardDescription>

          {activeTab !== 'verification' ? (
            <Input
              placeholder="输入 Trace ID，如 trace-123"
              value={traceIdInput}
              onChange={(event) => setTraceIdInput(event.target.value)}
              className="lg:max-w-sm"
            />
          ) : (
            <Input
              placeholder="输入 Answer ID，如 answer-42"
              value={answerIdInput}
              onChange={(event) => setAnswerIdInput(event.target.value)}
              className="lg:max-w-sm"
            />
          )}
        </CardHeader>
        <CardContent>{renderContent()}</CardContent>
      </Card>
    </section>
  );
};

export default Visualization;
