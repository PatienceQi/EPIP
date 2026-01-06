import { ChangeEvent, useCallback, useMemo, useRef, useState } from 'react';
import {
  Activity,
  AlertTriangle,
  BarChart3,
  Database,
  Download,
  RefreshCw,
  Shield,
  Upload,
} from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/cn';
import { post } from '@/lib/api';
import { formatNumber } from '@/lib/utils';
import {
  useDeleteOrphans,
  useGraphHealth,
  useGraphLabels,
  useGraphRelationshipTypes,
  useGraphStats,
  useImportNodes,
  useImportRelationships,
  useReindexDatabase,
} from '@/hooks/useGraph';
import { useTenantStore } from '@/stores/tenantStore';
import type {
  CreateNodeRequest,
  CreateRelationshipRequest,
  ExportFormat,
  GraphData,
} from '@/types/graph';

type MaintenanceOperation = 'reindex' | 'deleteOrphans';

interface DistributionEntry {
  name: string;
  count: number;
  percentage: number;
}

const escapeCsvCell = (value: unknown): string => {
  if (value === null || value === undefined) {
    return '';
  }
  const normalized =
    typeof value === 'string' ? value : typeof value === 'number' ? String(value) : JSON.stringify(value);
  const escaped = normalized.replace(/"/g, '""');
  return /[",\n]/.test(escaped) ? `"${escaped}"` : escaped;
};

const convertGraphDataToCsv = (graphData: GraphData): string => {
  const rows: string[][] = [
    ['section', 'id', 'label_or_type', 'start_node', 'end_node', 'properties'],
  ];

  graphData.nodes.forEach((node) => {
    rows.push([
      'node',
      node.id,
      node.labels.join('|'),
      '',
      '',
      JSON.stringify(node.properties ?? {}),
    ]);
  });

  graphData.relationships.forEach((rel) => {
    rows.push([
      'relationship',
      rel.id,
      rel.type,
      rel.start_node_id,
      rel.end_node_id,
      JSON.stringify(rel.properties ?? {}),
    ]);
  });

  return rows.map((row) => row.map((cell) => escapeCsvCell(cell)).join(',')).join('\n');
};

const downloadPayload = (payload: string, extension: string, mime: string) => {
  const blob = new Blob([payload], { type: mime });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `graph-export-${new Date().toISOString().replace(/[:.]/g, '-')}.${extension}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
};

const getDistribution = (source: Record<string, number> | undefined): DistributionEntry[] => {
  if (!source) return [];
  const entries = Object.entries(source);
  const total = entries.reduce((sum, [, value]) => sum + value, 0);

  return entries
    .sort((a, b) => b[1] - a[1])
    .map(([name, count]) => ({
      name,
      count,
      percentage: total === 0 ? 0 : Number(((count / total) * 100).toFixed(1)),
    }));
};

const getErrorMessage = (error: unknown): string =>
  error instanceof Error ? error.message : '操作失败，请稍后重试';

const GraphDataManager = () => {
  const currentTenant = useTenantStore((state) =>
    state.tenants.find((tenant) => tenant.tenant_id === state.currentTenantId)
  );
  const isAdmin = currentTenant?.config?.role === 'admin';

  const nodeFileInputRef = useRef<HTMLInputElement>(null);
  const relationshipFileInputRef = useRef<HTMLInputElement>(null);

  const { data: statsData, isLoading: statsLoading, error: statsError, refetch: refetchStats } =
    useGraphStats();
  const {
    data: healthData,
    isLoading: healthLoading,
    error: healthError,
    refetch: refetchHealth,
    isFetching: healthFetching,
  } = useGraphHealth();
  const { data: labelsData } = useGraphLabels();
  const { data: relationshipTypesData } = useGraphRelationshipTypes();

  const importNodesMutation = useImportNodes();
  const importRelationshipsMutation = useImportRelationships();
  const reindexMutation = useReindexDatabase();
  const deleteOrphansMutation = useDeleteOrphans();

  const [nodeImportMessage, setNodeImportMessage] = useState<string | null>(null);
  const [nodeImportError, setNodeImportError] = useState<string | null>(null);
  const [relationshipImportMessage, setRelationshipImportMessage] = useState<string | null>(null);
  const [relationshipImportError, setRelationshipImportError] = useState<string | null>(null);

  const [exportFormat, setExportFormat] = useState<ExportFormat>('json');
  const [exportIncludeRelationships, setExportIncludeRelationships] = useState(true);
  const [exportLabel, setExportLabel] = useState('');
  const [exportLimit, setExportLimit] = useState('');
  const [exportStatus, setExportStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(
    null
  );
  const [exportLoading, setExportLoading] = useState(false);

  const [confirmOperation, setConfirmOperation] = useState<MaintenanceOperation | null>(null);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);
  const [reindexError, setReindexError] = useState<string | null>(null);
  const [deleteMessage, setDeleteMessage] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  const labelDistribution = useMemo(
    () => getDistribution(statsData?.label_counts),
    [statsData?.label_counts]
  );
  const relationshipDistribution = useMemo(
    () => getDistribution(statsData?.relationship_type_counts),
    [statsData?.relationship_type_counts]
  );

  const refreshStatsAndHealth = useCallback(() => {
    void refetchStats();
    void refetchHealth();
  }, [refetchStats, refetchHealth]);

  const handleImport = useCallback(
    async (file: File, target: 'nodes' | 'relationships') => {
      try {
        const content = await file.text();
        const parsed = JSON.parse(content);
        if (target === 'nodes') {
          setNodeImportMessage(null);
          setNodeImportError(null);
          const nodes: CreateNodeRequest[] = Array.isArray(parsed)
            ? parsed
            : Array.isArray(parsed?.nodes)
              ? parsed.nodes
              : [];
          if (!nodes.length) {
            setNodeImportError('JSON 中缺少 nodes 数组');
            return;
          }
          importNodesMutation.mutate(
            { nodes },
            {
              onSuccess: (result) => {
                setNodeImportMessage(`成功导入 ${result.created} 个节点，失败 ${result.failed} 个`);
                setNodeImportError(result.errors?.[0] ? result.errors[0] : null);
                refreshStatsAndHealth();
              },
              onError: (error) => {
                setNodeImportError(getErrorMessage(error));
              },
            }
          );
        } else {
          setRelationshipImportMessage(null);
          setRelationshipImportError(null);
          const relationships: CreateRelationshipRequest[] = Array.isArray(parsed)
            ? parsed
            : Array.isArray(parsed?.relationships)
              ? parsed.relationships
              : [];
          if (!relationships.length) {
            setRelationshipImportError('JSON 中缺少 relationships 数组');
            return;
          }
          importRelationshipsMutation.mutate(
            { relationships },
            {
              onSuccess: (result) => {
                setRelationshipImportMessage(
                  `成功导入 ${result.created} 条关系，失败 ${result.failed} 条`
                );
                setRelationshipImportError(result.errors?.[0] ? result.errors[0] : null);
                refreshStatsAndHealth();
              },
              onError: (error) => {
                setRelationshipImportError(getErrorMessage(error));
              },
            }
          );
        }
      } catch (error) {
        if (target === 'nodes') {
          setNodeImportError('文件解析失败，请确认 JSON 格式');
        } else {
          setRelationshipImportError('文件解析失败，请确认 JSON 格式');
        }
      }
    },
    [
      importNodesMutation,
      importRelationshipsMutation,
      refreshStatsAndHealth,
    ]
  );

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>, target: 'nodes' | 'relationships') => {
    const file = event.target.files?.[0];
    if (file) {
      void handleImport(file, target);
      event.target.value = '';
    }
  };

  const handleExport = async () => {
    setExportStatus(null);
    setExportLoading(true);
    try {
      const payload = {
        format: exportFormat,
        include_relationships: exportIncludeRelationships,
        label: exportLabel || undefined,
        limit: exportLimit ? Number(exportLimit) : undefined,
      };
      const data = await post<GraphData>('/api/admin/graph/export', payload);
      if (exportFormat === 'json') {
        downloadPayload(JSON.stringify(data, null, 2), 'json', 'application/json');
      } else {
        downloadPayload(convertGraphDataToCsv(data), 'csv', 'text/csv');
      }
      setExportStatus({ type: 'success', message: `已生成 ${exportFormat.toUpperCase()} 导出文件` });
    } catch (error) {
      setExportStatus({ type: 'error', message: getErrorMessage(error) });
    } finally {
      setExportLoading(false);
    }
  };

  const handleMaintenanceConfirm = () => {
    if (!confirmOperation) return;

    const onSettled = () => {
      setConfirmOperation(null);
      refreshStatsAndHealth();
    };

    if (confirmOperation === 'reindex') {
      setReindexMessage(null);
      setReindexError(null);
      reindexMutation.mutate(undefined, {
        onSuccess: (result) => {
          setReindexMessage(result.message ?? '已触发索引重建');
        },
        onError: (error) => {
          setReindexError(getErrorMessage(error));
        },
        onSettled,
      });
    } else {
      setDeleteMessage(null);
      setDeleteError(null);
      deleteOrphansMutation.mutate(undefined, {
        onSuccess: (result) => {
          setDeleteMessage(result.message ?? '已删除孤立节点');
        },
        onError: (error) => {
          setDeleteError(getErrorMessage(error));
        },
        onSettled,
      });
    }
  };

  const renderDistributionCard = (
    title: string,
    description: string,
    entries: DistributionEntry[],
    emptyState: string
  ) => (
    <Card className="border-slate-100 shadow-none">
      <CardHeader className="space-y-1">
        <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
          <BarChart3 className="h-4 w-4 text-slate-400" />
          {title}
        </CardTitle>
        <p className="text-sm text-slate-500">{description}</p>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <p className="text-sm text-slate-400">{emptyState}</p>
        ) : (
          <ul className="space-y-3">
            {entries.slice(0, 8).map((entry) => (
              <li key={entry.name} className="flex items-center justify-between text-sm">
                <Badge variant="secondary" className="truncate">
                  {entry.name}
                </Badge>
                <div className="flex items-center gap-2 text-slate-500">
                  <span>{formatNumber(entry.count)}</span>
                  <span className="text-xs text-slate-400">{entry.percentage}%</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );

  if (!isAdmin) {
    return (
      <section className="space-y-6">
        <header className="space-y-2">
          <p className="text-sm uppercase tracking-wide text-slate-400">Neo4j</p>
          <h1 className="text-3xl font-semibold text-slate-900">图数据管理</h1>
          <p className="text-sm text-slate-500">仅管理员可访问此页面。</p>
        </header>
        <Card className="border-slate-100 bg-slate-50 shadow-none">
          <CardContent className="flex flex-col items-start gap-3 p-6">
            <Badge variant="secondary" className="bg-amber-100 text-amber-700">
              <Shield className="mr-1 h-3.5 w-3.5" />
              权限不足
            </Badge>
            <p className="text-sm text-slate-600">
              当前租户角色 {currentTenant?.config?.role ?? 'visitor'} 无法访问图数据库管理功能，
              请使用管理员租户登录。
            </p>
          </CardContent>
        </Card>
      </section>
    );
  }

  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <p className="text-sm uppercase tracking-wide text-slate-400">Neo4j</p>
          <h1 className="text-3xl font-semibold text-slate-900">图数据库数据管理</h1>
          <p className="text-sm text-slate-500">
            监控健康状态、批量导入导出数据，并执行索引及孤立节点维护操作。
          </p>
        </div>
        <Badge variant="secondary" className="self-start bg-slate-900 text-white">
          <Shield className="mr-1 h-3.5 w-3.5" />
          管理员
        </Badge>
      </header>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <Card className="border-slate-100 shadow-none">
          <CardHeader className="flex items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium text-slate-500">节点总数</CardTitle>
            <Database className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Spinner size="sm" label="节点统计加载中" />
            ) : (
              <p className="text-3xl font-semibold text-slate-900">
                {formatNumber(statsData?.node_count ?? 0)}
              </p>
            )}
            {statsError && <p className="mt-2 text-xs text-red-500">{getErrorMessage(statsError)}</p>}
          </CardContent>
        </Card>
        <Card className="border-slate-100 shadow-none">
          <CardHeader className="flex items-center justify-between space-y-0 pb-3">
            <CardTitle className="text-sm font-medium text-slate-500">关系总数</CardTitle>
            <Activity className="h-4 w-4 text-slate-400" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Spinner size="sm" label="关系统计加载中" />
            ) : (
              <p className="text-3xl font-semibold text-slate-900">
                {formatNumber(statsData?.relationship_count ?? 0)}
              </p>
            )}
          </CardContent>
        </Card>
        <Card className="border-slate-100 shadow-none">
          <CardHeader className="space-y-1">
            <CardTitle className="text-sm font-medium text-slate-500">标签总数</CardTitle>
            <p className="text-xs text-slate-400">来自元数据接口</p>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">
              {labelsData?.length ? formatNumber(labelsData.length) : '--'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(labelsData ?? []).slice(0, 5).map((label) => (
                <Badge key={label} variant="outline">
                  {label}
                </Badge>
              ))}
              {!labelsData?.length && <p className="text-xs text-slate-400">暂无标签</p>}
            </div>
          </CardContent>
        </Card>
        <Card className="border-slate-100 shadow-none">
          <CardHeader className="space-y-1">
            <CardTitle className="text-sm font-medium text-slate-500">关系类型总数</CardTitle>
            <p className="text-xs text-slate-400">来自元数据接口</p>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-slate-900">
              {relationshipTypesData?.length ? formatNumber(relationshipTypesData.length) : '--'}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {(relationshipTypesData ?? []).slice(0, 5).map((type) => (
                <Badge key={type} variant="outline">
                  {type}
                </Badge>
              ))}
              {!relationshipTypesData?.length && <p className="text-xs text-slate-400">暂无关系类型</p>}
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {renderDistributionCard(
          '标签分布',
          '展示当前最常见的节点标签及占比。',
          labelDistribution,
          '暂无标签分布数据。'
        )}
        {renderDistributionCard(
          '关系类型分布',
          '展示当前最常见的关系类型及占比。',
          relationshipDistribution,
          '暂无关系类型分布数据。'
        )}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="border-slate-100 shadow-none">
          <CardHeader className="flex items-center justify-between space-y-0 pb-2">
            <div>
              <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
                <Shield className="h-4 w-4 text-slate-400" />
                健康状态
              </CardTitle>
              <p className="text-sm text-slate-500">监控 Neo4j 连接与统计信息。</p>
            </div>
            <Button
              size="sm"
              variant="outline"
              className="gap-1"
              onClick={refreshStatsAndHealth}
              disabled={healthFetching}
            >
              <RefreshCw className={cn('h-4 w-4', healthFetching && 'animate-spin')} />
              刷新
            </Button>
          </CardHeader>
          <CardContent className="space-y-4">
            {healthLoading ? (
              <Spinner size="sm" label="健康状态加载中" />
            ) : (
              <>
                <div className="flex flex-wrap gap-2">
                  <Badge
                    className={cn(
                      'text-xs',
                      healthData?.status === 'healthy'
                        ? 'bg-emerald-50 text-emerald-700'
                        : 'bg-red-50 text-red-600'
                    )}
                  >
                    {healthData?.status === 'healthy' ? '健康' : '异常'}
                  </Badge>
                  <Badge
                    className={cn(
                      'text-xs',
                      healthData?.connected
                        ? 'bg-indigo-50 text-indigo-700'
                        : 'bg-amber-50 text-amber-700'
                    )}
                  >
                    {healthData?.connected ? '已连接' : '未连接'}
                  </Badge>
                </div>
                {healthError && <p className="text-sm text-red-500">{getErrorMessage(healthError)}</p>}
                {healthData?.stats && (
                  <div className="rounded-xl border border-slate-100 p-4">
                    <p className="text-xs font-medium uppercase text-slate-400">实时统计</p>
                    <div className="mt-2 grid gap-4 sm:grid-cols-2">
                      <div>
                        <p className="text-sm text-slate-500">节点</p>
                        <p className="text-lg font-semibold text-slate-900">
                          {formatNumber(healthData.stats.node_count)}
                        </p>
                      </div>
                      <div>
                        <p className="text-sm text-slate-500">关系</p>
                        <p className="text-lg font-semibold text-slate-900">
                          {formatNumber(healthData.stats.relationship_count)}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>
        <Card className="border-slate-100 shadow-none">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
              <Database className="h-4 w-4 text-slate-400" />
              元数据一览
            </CardTitle>
            <p className="text-sm text-slate-500">可用标签与关系类型将影响导入和导出配置。</p>
          </CardHeader>
          <CardContent className="space-y-4">
            <div>
              <p className="text-xs font-medium uppercase text-slate-400">
                标签 ({labelsData?.length ?? 0})
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(labelsData ?? []).length ? (
                  labelsData!.map((label) => (
                    <Badge key={label} variant="outline">
                      {label}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">尚未采集到标签</p>
                )}
              </div>
            </div>
            <div>
              <p className="text-xs font-medium uppercase text-slate-400">
                关系类型 ({relationshipTypesData?.length ?? 0})
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {(relationshipTypesData ?? []).length ? (
                  relationshipTypesData!.map((type) => (
                    <Badge key={type} variant="outline">
                      {type}
                    </Badge>
                  ))
                ) : (
                  <p className="text-sm text-slate-400">尚未采集到关系类型</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-100 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <Upload className="h-4 w-4 text-slate-400" />
            批量导入
          </CardTitle>
          <p className="text-sm text-slate-500">上传 JSON 文件批量导入节点与关系。</p>
        </CardHeader>
        <CardContent className="grid gap-6 md:grid-cols-2">
          <div className="rounded-xl border border-dashed border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">节点导入</p>
                <p className="text-sm text-slate-500">支持包含 nodes 数组的 JSON。</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={() => nodeFileInputRef.current?.click()}
                disabled={importNodesMutation.isPending}
              >
                {importNodesMutation.isPending ? (
                  <Spinner size="sm" label="上传中" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                导入
              </Button>
              <input
                ref={nodeFileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => handleFileInputChange(event, 'nodes')}
              />
            </div>
            <p className="mt-3 text-xs text-slate-400">
              每条记录需包含 labels (string[]) 与 properties (object) 字段。
            </p>
            {nodeImportMessage && <p className="mt-3 text-sm text-emerald-600">{nodeImportMessage}</p>}
            {nodeImportError && (
              <p className="mt-2 text-sm text-red-500">
                <AlertTriangle className="mr-1 inline-block h-4 w-4" />
                {nodeImportError}
              </p>
            )}
          </div>
          <div className="rounded-xl border border-dashed border-slate-200 p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-slate-900">关系导入</p>
                <p className="text-sm text-slate-500">支持包含 relationships 数组的 JSON。</p>
              </div>
              <Button
                variant="outline"
                size="sm"
                className="gap-1"
                onClick={() => relationshipFileInputRef.current?.click()}
                disabled={importRelationshipsMutation.isPending}
              >
                {importRelationshipsMutation.isPending ? (
                  <Spinner size="sm" label="上传中" />
                ) : (
                  <Upload className="h-4 w-4" />
                )}
                导入
              </Button>
              <input
                ref={relationshipFileInputRef}
                type="file"
                accept="application/json,.json"
                className="hidden"
                onChange={(event) => handleFileInputChange(event, 'relationships')}
              />
            </div>
            <p className="mt-3 text-xs text-slate-400">
              每条记录需包含 start_node_id、end_node_id、type 与 properties (可选)。
            </p>
            {relationshipImportMessage && (
              <p className="mt-3 text-sm text-emerald-600">{relationshipImportMessage}</p>
            )}
            {relationshipImportError && (
              <p className="mt-2 text-sm text-red-500">
                <AlertTriangle className="mr-1 inline-block h-4 w-4" />
                {relationshipImportError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-100 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <Download className="h-4 w-4 text-slate-400" />
            数据导出
          </CardTitle>
          <p className="text-sm text-slate-500">生成 JSON 或 CSV 文件以便备份与迁移。</p>
        </CardHeader>
        <CardContent className="space-y-5">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium text-slate-700">导出格式</span>
            <div className="flex gap-2">
              {(['json', 'csv'] as ExportFormat[]).map((format) => (
                <Button
                  key={format}
                  type="button"
                  size="sm"
                  variant={exportFormat === format ? 'default' : 'outline'}
                  onClick={() => setExportFormat(format)}
                >
                  {format.toUpperCase()}
                </Button>
              ))}
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="text-sm font-medium text-slate-700">标签过滤</label>
              <select
                className="mt-1 h-10 w-full rounded-lg border border-slate-200 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
                value={exportLabel}
                onChange={(event) => setExportLabel(event.target.value)}
              >
                <option value="">全部标签</option>
                {(labelsData ?? []).map((label) => (
                  <option key={label} value={label}>
                    {label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">数量上限</label>
              <Input
                type="number"
                min="0"
                className="mt-1"
                placeholder="默认不限"
                value={exportLimit}
                onChange={(event) => setExportLimit(event.target.value)}
              />
            </div>
            <div className="flex items-center gap-2 pt-6">
              <input
                id="include-relationships"
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300 text-slate-900 focus:ring-slate-900"
                checked={exportIncludeRelationships}
                onChange={(event) => setExportIncludeRelationships(event.target.checked)}
              />
              <label htmlFor="include-relationships" className="text-sm text-slate-700">
                包含关系数据
              </label>
            </div>
          </div>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-slate-500">
              导出数据遵循管理员权限，可用于备份或迁移至其他环境。
            </p>
            <Button
              className="gap-2"
              onClick={handleExport}
              disabled={exportLoading}
            >
              {exportLoading ? (
                <Spinner size="sm" label="导出中" />
              ) : (
                <Download className="h-4 w-4" />
              )}
              下载数据
            </Button>
          </div>
          {exportStatus && (
            <p
              className={cn(
                'text-sm',
                exportStatus.type === 'success' ? 'text-emerald-600' : 'text-red-500'
              )}
            >
              {exportStatus.message}
            </p>
          )}
        </CardContent>
      </Card>

      <Card className="border-slate-100 shadow-none">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base font-semibold text-slate-900">
            <RefreshCw className="h-4 w-4 text-slate-400" />
            维护工具
          </CardTitle>
          <p className="text-sm text-slate-500">执行索引重建与孤立节点清理，操作前需确认。</p>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          <div className="rounded-xl border border-slate-100 p-4">
            <p className="font-medium text-slate-900">重建索引</p>
            <p className="mt-1 text-sm text-slate-500">
              重新创建常用标签的 name 属性索引，提升查询性能。
            </p>
            <div className="mt-4 flex items-center justify-between">
              <Button
                variant="outline"
                className="gap-2"
                onClick={() => setConfirmOperation('reindex')}
                disabled={reindexMutation.isPending}
              >
                {reindexMutation.isPending && <Spinner size="sm" label="执行中" />}
                执行
              </Button>
            </div>
            {reindexMessage && <p className="mt-3 text-sm text-emerald-600">{reindexMessage}</p>}
            {reindexError && (
              <p className="mt-2 text-sm text-red-500">
                <AlertTriangle className="mr-1 inline-block h-4 w-4" />
                {reindexError}
              </p>
            )}
          </div>
          <div className="rounded-xl border border-slate-100 p-4">
            <p className="font-medium text-slate-900">删除孤立节点</p>
            <p className="mt-1 text-sm text-slate-500">删除无关系的节点，保持图结构整洁。</p>
            <div className="mt-4 flex items-center justify-between">
              <Button
                variant="destructive"
                className="gap-2"
                onClick={() => setConfirmOperation('deleteOrphans')}
                disabled={deleteOrphansMutation.isPending}
              >
                {deleteOrphansMutation.isPending && <Spinner size="sm" label="执行中" />}
                清理
              </Button>
            </div>
            {deleteMessage && <p className="mt-3 text-sm text-emerald-600">{deleteMessage}</p>}
            {deleteError && (
              <p className="mt-2 text-sm text-red-500">
                <AlertTriangle className="mr-1 inline-block h-4 w-4" />
                {deleteError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Modal
        open={Boolean(confirmOperation)}
        title={
          confirmOperation === 'reindex'
            ? '确认重建索引'
            : confirmOperation === 'deleteOrphans'
              ? '确认删除孤立节点'
              : ''
        }
        onClose={() => setConfirmOperation(null)}
        footer={
          <div className="flex justify-end gap-3">
            <Button variant="outline" onClick={() => setConfirmOperation(null)}>
              取消
            </Button>
            <Button
              variant={confirmOperation === 'deleteOrphans' ? 'destructive' : 'default'}
              onClick={handleMaintenanceConfirm}
              disabled={reindexMutation.isPending || deleteOrphansMutation.isPending}
            >
              确认
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          {confirmOperation === 'reindex'
            ? '该操作将重新创建常用标签的索引，可能对数据库造成瞬时压力，确定继续吗？'
            : '该操作将批量删除无关系节点，数据无法恢复，请再次确认。'}
        </p>
      </Modal>
    </section>
  );
};

export default GraphDataManager;
