import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { AlertTriangle, Clock, History, Loader2, Play, Sparkles, Trash2 } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useExecuteCypher } from '@/hooks/useGraph';
import { useTenantStore } from '@/stores/tenantStore';
import type { CypherExecuteRequest, CypherExecuteResponse } from '@/types/graph';

const HISTORY_STORAGE_KEY = 'cypher-console-history';
const HISTORY_LIMIT = 15;
const DEFAULT_QUERY = 'MATCH (n) RETURN n LIMIT 25';
const HIGHLIGHT_KEYWORDS = ['MATCH', 'WHERE', 'RETURN', 'WITH', 'CREATE', 'DELETE', 'SET', 'MERGE', 'CALL'];
const WRITE_KEYWORDS = ['CREATE', 'MERGE', 'DELETE', 'SET', 'DROP', 'REMOVE'];

interface CypherHistoryItem {
  id: string;
  query: string;
  executedAt: number;
  isWrite: boolean;
  rowCount: number;
  executionTime: number;
}

const detectWriteQuery = (text: string): boolean => {
  if (!text) return false;
  const normalized = text.toUpperCase();
  return WRITE_KEYWORDS.some((keyword) => new RegExp(`\\b${keyword}\\b`).test(normalized));
};

const highlightQueryText = (text: string): ReactNode[] => {
  if (!text) return [];
  return text.split(/(\s+)/).map((segment, index) => {
    const upper = segment.toUpperCase();
    if (HIGHLIGHT_KEYWORDS.includes(upper)) {
      return (
        <span key={`highlight-${index}`} className="text-indigo-600">
          {segment}
        </span>
      );
    }
    return <span key={`highlight-${index}`}>{segment}</span>;
  });
};

const readHistoryFromStorage = (): CypherHistoryItem[] => {
  if (typeof window === 'undefined') return [];
  const raw = window.localStorage.getItem(HISTORY_STORAGE_KEY);
  if (!raw) return [];

  try {
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];

    return parsed
      .slice(0, HISTORY_LIMIT)
      .map((item, index) => ({
        id: typeof item.id === 'string' ? item.id : `${item.executedAt ?? Date.now()}-${index}`,
        query: typeof item.query === 'string' ? item.query : '',
        executedAt: typeof item.executedAt === 'number' ? item.executedAt : Date.now(),
        isWrite: Boolean(item.isWrite),
        rowCount: typeof item.rowCount === 'number' ? item.rowCount : 0,
        executionTime: typeof item.executionTime === 'number' ? item.executionTime : 0,
      }))
      .filter((entry) => entry.query);
  } catch {
    return [];
  }
};

const formatDateTime = (timestamp: number): string =>
  new Date(timestamp).toLocaleString();

const renderCellValue = (value: unknown): ReactNode => {
  if (value === null || value === undefined) return <span>-</span>;
  if (typeof value === 'object') {
    return (
      <pre className="whitespace-pre-wrap font-mono text-xs text-slate-800">
        {JSON.stringify(value, null, 2)}
      </pre>
    );
  }
  return <span>{String(value)}</span>;
};

const CypherConsole = () => {
  const [query, setQuery] = useState(DEFAULT_QUERY);
  const [parametersJson, setParametersJson] = useState('');
  const [history, setHistory] = useState<CypherHistoryItem[]>([]);
  const [historyFilter, setHistoryFilter] = useState('');
  const [result, setResult] = useState<CypherExecuteResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const executeCypher = useExecuteCypher();
  const currentTenant = useTenantStore((state) =>
    state.tenants.find((tenant) => tenant.tenant_id === state.currentTenantId)
  );
  const tenantRole = (currentTenant?.config as { role?: string } | undefined)?.role;
  const isAdmin = tenantRole === 'admin';

  const trimmedQuery = query.trim();
  const isPotentialWrite = useMemo(() => detectWriteQuery(trimmedQuery), [trimmedQuery]);
  const highlightedQuery = useMemo(() => highlightQueryText(query), [query]);
  const filteredHistory = useMemo(() => {
    const filter = historyFilter.trim().toLowerCase();
    if (!filter) return history;
    return history.filter((item) => item.query.toLowerCase().includes(filter));
  }, [history, historyFilter]);

  useEffect(() => {
    setHistory(readHistoryFromStorage());
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(HISTORY_STORAGE_KEY, JSON.stringify(history));
  }, [history]);

  const addHistoryEntry = useCallback((entry: Omit<CypherHistoryItem, 'id'>) => {
    setHistory((prev) => {
      const deduped = prev.filter((item) => item.query !== entry.query);
      const next: CypherHistoryItem[] = [
        { ...entry, id: `${entry.executedAt}-${entry.query.length}` },
        ...deduped,
      ];
      return next.slice(0, HISTORY_LIMIT);
    });
  }, []);

  const removeHistoryEntry = useCallback((id: string) => {
    setHistory((prev) => prev.filter((item) => item.id !== id));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
    setHistoryFilter('');
  }, []);

  const handleSelectHistory = useCallback((entry: CypherHistoryItem) => {
    setQuery(entry.query);
    setError(null);
  }, []);

  const handleResetQuery = useCallback(() => {
    setQuery(DEFAULT_QUERY);
    setParametersJson('');
    setResult(null);
    setError(null);
  }, []);

  const handleExecuteQuery = useCallback(async () => {
    if (!trimmedQuery) {
      setError('请输入要执行的 Cypher 查询。');
      return;
    }

    if (isPotentialWrite && !isAdmin) {
      setError('当前租户没有写操作权限，请调整为只读查询。');
      return;
    }

    let parameters: CypherExecuteRequest['parameters'] | undefined;
    if (parametersJson.trim()) {
      try {
        const parsed = JSON.parse(parametersJson);
        if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
          setError('参数必须是一个 JSON 对象。');
          return;
        }
        parameters = parsed;
      } catch {
        setError('参数必须是合法的 JSON 字符串。');
        return;
      }
    }

    setError(null);
    const payload: CypherExecuteRequest = { query: trimmedQuery };
    if (parameters) {
      payload.parameters = parameters;
    }

    try {
      const response = await executeCypher.mutateAsync(payload);
      setResult(response);
      addHistoryEntry({
        query: trimmedQuery,
        executedAt: Date.now(),
        isWrite: response.is_write_query,
        rowCount: response.data.length,
        executionTime: response.execution_time_ms,
      });
    } catch (mutationError) {
      const message =
        mutationError instanceof Error ? mutationError.message : '执行失败，请稍后再试。';
      setError(message);
    }
  }, [trimmedQuery, isPotentialWrite, isAdmin, parametersJson, executeCypher, addHistoryEntry]);

  const runDisabled =
    !trimmedQuery || executeCypher.isPending || (!isAdmin && isPotentialWrite);
  const rowCount = result?.data.length ?? 0;
  const executionTime = result?.execution_time_ms ?? 0;
  const isWriteResult = result?.is_write_query ?? isPotentialWrite;

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-[2fr_1fr]">
        <Card className="h-full">
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <CardTitle>Cypher 查询控制台</CardTitle>
                <CardDescription>
                  直接执行 Cypher 查询，{isAdmin ? '支持写操作，请谨慎修改数据。' : '当前为租户只读模式。'}
                </CardDescription>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={isPotentialWrite ? 'destructive' : 'secondary'}>
                  {isPotentialWrite ? '写操作' : '读操作'}
                </Badge>
                <Badge variant={isAdmin ? 'secondary' : 'outline'}>
                  {isAdmin ? '管理员' : '租户只读'}
                </Badge>
                <Button variant="outline" size="sm" onClick={handleResetQuery}>
                  重置
                </Button>
                <Button onClick={handleExecuteQuery} disabled={runDisabled}>
                  {executeCypher.isPending ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      执行中...
                    </>
                  ) : (
                    <>
                      <Play className="mr-2 h-4 w-4" />
                      执行查询
                    </>
                  )}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-slate-700">Cypher 查询</label>
                <textarea
                  className="mt-2 min-h-[200px] w-full rounded-xl border border-slate-200 bg-white/80 p-3 font-mono text-sm text-slate-900 shadow-inner focus:border-indigo-500 focus:outline-none"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="MATCH (n) RETURN n LIMIT 25"
                />
              </div>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-slate-700">参数 (JSON，可选)</label>
                  <Input
                    className="mt-2 font-mono text-sm"
                    placeholder='例如: {"limit": 25}'
                    value={parametersJson}
                    onChange={(event) => setParametersJson(event.target.value)}
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-slate-700">关键字速查</label>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {HIGHLIGHT_KEYWORDS.map((keyword) => (
                      <Badge key={keyword} variant="secondary" className="font-mono">
                        {keyword}
                      </Badge>
                    ))}
                  </div>
                </div>
              </div>
              <div>
                <div className="flex items-center gap-2 text-xs font-semibold uppercase text-slate-500">
                  <Sparkles className="h-4 w-4 text-indigo-500" />
                  语法高亮提示
                </div>
                <div className="mt-2 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-3">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-slate-800">
                    {highlightedQuery.length > 0 ? (
                      highlightedQuery
                    ) : (
                      <span className="text-slate-400">在上方输入查询语句以查看高亮信息。</span>
                    )}
                  </pre>
                </div>
              </div>
              {(isPotentialWrite || result?.is_write_query) && (
                <div
                  className={`flex items-start gap-2 rounded-2xl border px-3 py-2 text-sm ${
                    isAdmin ? 'border-amber-300 bg-amber-50 text-amber-900' : 'border-red-300 bg-red-50 text-red-800'
                  }`}
                >
                  <AlertTriangle className="mt-0.5 h-4 w-4" />
                  <div>
                    <p className="font-semibold">
                      {isAdmin ? '检测到写操作' : '当前租户禁止写操作'}
                    </p>
                    <p className="text-xs">
                      {isAdmin
                        ? '该查询可能会修改图数据，请确认后再执行。'
                        : '请调整为 MATCH / RETURN 等只读语句后再执行。'}
                    </p>
                  </div>
                </div>
              )}
              {error && <p className="text-sm text-red-600">{error}</p>}
            </div>
          </CardContent>
        </Card>

        <Card className="h-full">
          <CardHeader>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <History className="h-5 w-5 text-slate-500" />
                <div>
                  <CardTitle>查询历史</CardTitle>
                  <CardDescription>最多保留最近 {HISTORY_LIMIT} 条记录。</CardDescription>
                </div>
              </div>
              {history.length > 0 && (
                <Button variant="outline" size="sm" onClick={clearHistory}>
                  <Trash2 className="mr-1.5 h-4 w-4" />
                  清空
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <Input
                placeholder="搜索历史查询..."
                value={historyFilter}
                onChange={(event) => setHistoryFilter(event.target.value)}
              />
              <div className="space-y-3">
                {filteredHistory.length === 0 ? (
                  <p className="text-sm text-slate-500">暂无历史记录，执行查询后会自动保存。</p>
                ) : (
                  filteredHistory.map((entry) => (
                    <div key={entry.id} className="rounded-2xl border border-slate-200 p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="flex items-center gap-2">
                          <Badge variant={entry.isWrite ? 'destructive' : 'secondary'}>
                            {entry.isWrite ? '写操作' : '读操作'}
                          </Badge>
                          <Badge variant="outline" className="font-mono">
                            {entry.rowCount} 行
                          </Badge>
                        </div>
                        <span className="text-xs text-slate-500">
                          {formatDateTime(entry.executedAt)}
                        </span>
                      </div>
                      <p className="mt-2 max-h-20 overflow-y-auto font-mono text-xs text-slate-800 whitespace-pre-wrap">
                        {entry.query}
                      </p>
                      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3.5 w-3.5" />
                          {entry.executionTime} ms
                        </span>
                        <div className="flex items-center gap-2">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleSelectHistory(entry)}
                          >
                            载入
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => removeHistoryEntry(entry.id)}
                          >
                            删除
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <CardTitle>查询结果</CardTitle>
              <CardDescription>
                {result ? '最近一次执行的返回数据。' : '执行查询后将在此显示结果。'}
              </CardDescription>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline" className="gap-1 font-mono">
                <Clock className="h-3.5 w-3.5" />
                {executionTime} ms
              </Badge>
              <Badge variant="outline" className="font-mono">
                {rowCount} 行
              </Badge>
              <Badge variant={isWriteResult ? 'destructive' : 'secondary'}>
                {isWriteResult ? '写操作' : '读操作'}
              </Badge>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {result ? (
            result.data.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-slate-200 text-sm">
                  <thead>
                    <tr className="bg-slate-50">
                      {result.columns.map((column) => (
                        <th
                          key={column}
                          className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-slate-500"
                        >
                          {column}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100">
                    {result.data.map((row, rowIndex) => (
                      <tr key={`row-${rowIndex}`} className="bg-white">
                        {result.columns.map((column) => (
                          <td
                            key={`${rowIndex}-${column}`}
                            className="px-3 py-2 align-top font-mono text-xs text-slate-800"
                          >
                            {renderCellValue(row[column])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-sm text-slate-500">查询执行成功，但没有返回数据。</p>
            )
          ) : (
            <p className="text-sm text-slate-500">暂无结果，请先在上方执行查询。</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default CypherConsole;
