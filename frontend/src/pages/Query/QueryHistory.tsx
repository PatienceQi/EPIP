import { useMemo, useState } from 'react';
import { CalendarClock, Clock4, Filter, Search, Trash2 } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { useQueryStore } from '@/stores/queryStore';
import type { QueryHistoryItem } from '@/stores/queryStore';

const formatDateLabel = (timestamp: number) => {
  const current = new Date();
  const target = new Date(timestamp);
  const isSameDay = current.toDateString() === target.toDateString();
  const yesterday = new Date(current);
  yesterday.setDate(current.getDate() - 1);

  if (isSameDay) {
    return '今天';
  }
  if (yesterday.toDateString() === target.toDateString()) {
    return '昨天';
  }

  return target.toLocaleDateString('zh-CN', {
    month: 'numeric',
    day: 'numeric',
    weekday: 'short',
  });
};

const formatTime = (timestamp: number) =>
  new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(timestamp));

const QueryHistory = () => {
  const { queryHistory, clearHistory, setCurrentQuery } = useQueryStore((state) => ({
    queryHistory: state.queryHistory,
    clearHistory: state.clearHistory,
    setCurrentQuery: state.setCurrentQuery,
  }));
  const [searchTerm, setSearchTerm] = useState('');

  const filteredHistory = useMemo(() => {
    if (!searchTerm) return queryHistory;
    const keyword = searchTerm.toLowerCase();
    return queryHistory.filter((item) => {
      const queryText = item.request.query.toLowerCase();
      const answerText = (item.response.answer ?? '').toLowerCase();
      return queryText.includes(keyword) || answerText.includes(keyword);
    });
  }, [queryHistory, searchTerm]);

  const groupedHistory = useMemo(() => {
    const groups = new Map<string, QueryHistoryItem[]>();

    filteredHistory.forEach((item) => {
      const label = formatDateLabel(item.timestamp);
      if (!groups.has(label)) {
        groups.set(label, []);
      }
      groups.get(label)?.push(item);
    });

    return Array.from(groups.entries());
  }, [filteredHistory]);

  const handleSelect = (item: QueryHistoryItem) => {
    setCurrentQuery(item.request.query);
  };

  const handleClear = () => {
    if (queryHistory.length === 0) return;
    clearHistory();
  };

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <div className="flex items-center justify-between gap-3">
          <div>
            <CardTitle className="text-xl">历史记录</CardTitle>
            <CardDescription>最近 50 条查询，按日期分组存档。</CardDescription>
          </div>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="gap-1 text-slate-500"
            onClick={handleClear}
            disabled={queryHistory.length === 0}
          >
            <Trash2 className="h-4 w-4" />
            清空
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            placeholder="搜索历史查询..."
            className="w-full border-slate-200 pl-10 pr-4"
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
          />
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Filter className="h-3.5 w-3.5" />
          支持按问题或答案关键字快速过滤。
        </div>
        <div className="flex-1 overflow-y-auto pr-2">
          {groupedHistory.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-3 text-center text-slate-400">
              <CalendarClock className="h-10 w-10 text-slate-300" />
              <div>
                <p className="font-medium text-slate-600">暂无历史记录</p>
                <p className="text-sm">执行查询后将自动保存至此。</p>
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {groupedHistory.map(([dateLabel, items]) => (
                <div key={dateLabel}>
                  <p className="mb-3 text-xs font-semibold uppercase tracking-wide text-slate-400">
                    {dateLabel}
                  </p>
                  <div className="space-y-2">
                    {items.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        onClick={() => handleSelect(item)}
                        className="w-full rounded-2xl border border-slate-100 bg-white p-3 text-left text-sm transition hover:border-slate-200 hover:bg-slate-50"
                      >
                        <p
                          className="font-medium text-slate-700"
                          style={{
                            display: '-webkit-box',
                            WebkitLineClamp: 2,
                            WebkitBoxOrient: 'vertical',
                            overflow: 'hidden',
                          }}
                        >
                          {item.request.query}
                        </p>
                        <div className="mt-2 flex items-center justify-between text-xs text-slate-500">
                          <span className="inline-flex items-center gap-1">
                            <Clock4 className="h-3.5 w-3.5" />
                            {formatTime(item.timestamp)}
                          </span>
                          <span className="truncate text-slate-400">
                            {(item.response.answer ?? '').slice(0, 40) || '无答案'}
                          </span>
                        </div>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default QueryHistory;
