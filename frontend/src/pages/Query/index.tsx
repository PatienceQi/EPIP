import { useCallback, useMemo, useState } from 'react';
import { PanelLeftClose, PanelLeftOpen } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/cn';
import type { QueryResponse } from '@/types/api';

import QueryHistory from './QueryHistory';
import QueryInput from './QueryInput';
import QueryResult from './QueryResult';

const Query = () => {
  const [latestResult, setLatestResult] = useState<QueryResponse | null>(null);
  const [status, setStatus] = useState<{ loading: boolean; error: string | null }>({
    loading: false,
    error: null,
  });
  const [historyOpen, setHistoryOpen] = useState(true);

  const handleResult = useCallback((response: QueryResponse) => {
    setLatestResult(response);
  }, []);

  const handleStatusChange = useCallback((next: { loading: boolean; error?: string | null }) => {
    setStatus({ loading: next.loading, error: next.error ?? null });
    if (next.loading) {
      setLatestResult(null);
    }
  }, []);

  const layoutClass = useMemo(
    () =>
      historyOpen
        ? 'lg:grid-cols-[320px_minmax(0,1fr)_minmax(0,1fr)]'
        : 'lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]',
    [historyOpen]
  );

  return (
    <section className="flex flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">
            EPIP Query Center
          </p>
          <h1 className="text-2xl font-semibold text-slate-900">查询中心</h1>
          <p className="mt-1 text-sm text-slate-600">
            左侧快速检索历史，中央编辑查询，右侧即时查看 AI 生成的答复与轨迹。
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="gap-2 text-slate-600"
          onClick={() => setHistoryOpen((value) => !value)}
        >
          {historyOpen ? <PanelLeftClose className="h-4 w-4" /> : <PanelLeftOpen className="h-4 w-4" />}
          {historyOpen ? '折叠历史' : '展开历史'}
        </Button>
      </div>
      <div className={cn('grid grid-cols-1 gap-6', layoutClass)}>
        {historyOpen && (
          <div className="hidden lg:block">
            <QueryHistory />
          </div>
        )}
        <div>
          <QueryInput onResult={handleResult} onStatusChange={handleStatusChange} />
        </div>
        <div className="min-h-[480px]">
          <QueryResult result={latestResult} isLoading={status.loading} errorMessage={status.error} />
        </div>
      </div>
    </section>
  );
};

export default Query;
