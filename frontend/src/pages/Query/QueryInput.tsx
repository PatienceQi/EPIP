import { Keyboard, SendHorizontal, Sparkles } from 'lucide-react';
import { type KeyboardEvent, useMemo, useState } from 'react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { cn } from '@/lib/cn';
import { useQuery as useExecuteQuery } from '@/hooks/useApi';
import { useQueryStore } from '@/stores/queryStore';
import { QueryResponse } from '@/types/api';

interface QueryInputProps {
  onResult: (response: QueryResponse) => void;
  onStatusChange?: (status: { loading: boolean; error?: string | null }) => void;
}

const sampleQueries = [
  '总结下 Neo4j 最新的发布亮点？',
  'EPIP 中 Redis 的缓存命中率趋势如何？',
  '请列出当前接入的租户及其状态。',
];

const QueryInput = ({ onResult, onStatusChange }: QueryInputProps) => {
  const currentQuery = useQueryStore((state) => state.currentQuery);
  const setCurrentQuery = useQueryStore((state) => state.setCurrentQuery);
  const queryMutation = useExecuteQuery();
  const [localError, setLocalError] = useState<string | null>(null);

  const isSubmitting = queryMutation.isPending;
  const disabled = isSubmitting || !currentQuery.trim();

  const handleSubmit = async () => {
    const text = currentQuery.trim();
    if (!text) {
      const message = '请输入查询内容';
      setLocalError(message);
      onStatusChange?.({ loading: false, error: message });
      return;
    }

    setLocalError(null);
    onStatusChange?.({ loading: true, error: null });

    try {
      const response = await queryMutation.mutateAsync({ query: text });
      onResult(response);
      onStatusChange?.({ loading: false, error: null });
    } catch (error) {
      const message =
        error instanceof Error ? error.message : '查询失败，请稍后重试。';
      setLocalError(message);
      onStatusChange?.({ loading: false, error: message });
    }
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
      event.preventDefault();
      handleSubmit();
    }
  };

  const handleSamplePick = (value: string) => {
    setLocalError(null);
    setCurrentQuery(value);
  };

  const helperText = useMemo(() => {
    if (localError) {
      return (
        <span className="text-sm text-red-500" role="alert">
          {localError}
        </span>
      );
    }

    return (
      <span className="text-sm text-slate-500">
        支持自然语言与结构化语句，<kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> 快速发送。
      </span>
    );
  }, [localError]);

  return (
    <Card className="flex h-full flex-col">
      <CardHeader>
        <CardTitle className="text-xl">查询输入</CardTitle>
        <CardDescription>描述你的问题或需求，系统会自动匹配知识库与推理链路。</CardDescription>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        <form
          className="flex flex-1 flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            handleSubmit();
          }}
        >
          <label className="flex-1">
            <span className="sr-only">查询内容</span>
            <textarea
              className={cn(
                'min-h-[220px] w-full flex-1 resize-none rounded-2xl border border-slate-200 bg-slate-50/70 px-4 py-3 text-base text-slate-900 shadow-inner focus:border-slate-400 focus:bg-white focus:outline-none focus:ring-2 focus:ring-slate-900/10',
                localError && 'border-red-300 focus:border-red-400 focus:ring-red-300/40'
              )}
              value={currentQuery}
              placeholder="例如：帮我分析一下 Neo4j 与 Redis 在本月的资源使用情况，并给出优化建议。"
              onChange={(event) => {
                setLocalError(null);
                setCurrentQuery(event.target.value);
              }}
              onKeyDown={handleKeyDown}
              disabled={isSubmitting}
              rows={10}
            />
          </label>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            {helperText}
            <Button
              type="submit"
              disabled={disabled}
              className="inline-flex min-w-[120px] items-center justify-center gap-2"
            >
              {isSubmitting ? (
                <>
                  <Spinner size="sm" label="执行中" />
                  <span>执行中...</span>
                </>
              ) : (
                <>
                  <SendHorizontal className="h-4 w-4" />
                  <span>发送查询</span>
                </>
              )}
            </Button>
          </div>
        </form>
        <div>
          <div className="flex items-center gap-2 text-sm font-medium text-slate-600">
            <Sparkles className="h-4 w-4 text-amber-500" />
            示例查询
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {sampleQueries.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => handleSamplePick(suggestion)}
                className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm transition hover:border-slate-300 hover:bg-slate-50"
              >
                <Keyboard className="h-3.5 w-3.5 text-slate-400" />
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export default QueryInput;
