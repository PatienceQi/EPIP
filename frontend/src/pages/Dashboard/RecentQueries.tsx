import { useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowUpRight, Clock4, History, Search } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { cn } from '@/lib/cn';
import { useQueryStore } from '@/stores/queryStore';

interface RecentQueriesProps {
  className?: string;
}

const formatTime = (timestamp: number) =>
  new Intl.DateTimeFormat('zh-CN', {
    hour12: false,
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp));

const RecentQueries = ({ className }: RecentQueriesProps) => {
  const navigate = useNavigate();
  const history = useQueryStore((state) => state.queryHistory);

  const recentItems = useMemo(() => history.slice(0, 5), [history]);

  const handleNavigate = (traceId?: string) => {
    if (traceId) {
      navigate(`/visualization/trace/${traceId}`);
      return;
    }
    navigate('/query');
  };

  return (
    <Card className={cn('h-full border-slate-100 shadow-none', className)}>
      <CardHeader className="border-b border-slate-100 pb-5">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-50 text-slate-600">
            <History className="h-5 w-5" />
          </div>
          <div>
            <CardTitle className="text-base text-slate-900">最近查询</CardTitle>
            <p className="text-sm text-slate-500">查看最新 5 条查询并快速跳转详情</p>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {recentItems.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 px-6 py-10 text-center text-sm text-slate-500">
            <Search className="h-8 w-8 text-slate-300" />
            <p>暂无查询记录，去查询中心发起第一条请求吧。</p>
          </div>
        ) : (
          <ul className="divide-y divide-slate-100">
            {recentItems.map((item) => {
              const traceId = item.response.trace_id as string | undefined;
              const isError = 'error' in item.response;
              const statusLabel = isError ? '失败' : '成功';
              const statusColor = isError ? 'bg-rose-50 text-rose-600' : 'bg-emerald-50 text-emerald-600';

              return (
                <li key={item.id}>
                  <button
                    type="button"
                    onClick={() => handleNavigate(traceId)}
                    className="flex w-full items-start gap-3 px-6 py-4 text-left transition hover:bg-slate-50"
                  >
                    <div className="mt-0.5 rounded-full bg-slate-100 p-2 text-slate-600">
                      <Clock4 className="h-4 w-4" />
                    </div>
                    <div className="flex flex-1 flex-col gap-2">
                      <div className="flex items-start justify-between gap-4">
                        <p className="text-sm font-medium text-slate-900">
                          {item.request.query || 'Graph 查询'}
                        </p>
                        <Badge className={cn('border-none px-2 py-0 text-xs', statusColor)} variant="secondary">
                          {statusLabel}
                        </Badge>
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                        <span>{formatTime(item.timestamp)}</span>
                        {traceId && (
                          <span className="inline-flex items-center gap-1 text-indigo-600">
                            Trace #{traceId.slice(0, 6)}
                          </span>
                        )}
                      </div>
                    </div>
                    <ArrowUpRight className="h-4 w-4 text-slate-400" />
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
};

export default RecentQueries;
