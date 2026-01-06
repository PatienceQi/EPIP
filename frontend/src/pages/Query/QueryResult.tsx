import { type ReactNode, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Check,
  Clipboard,
  ExternalLink,
  FileText,
  GitBranch,
  LineChart,
  ShieldCheck,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import type { QueryResponse } from '@/types/api';

interface QueryResultProps {
  result: QueryResponse | null;
  isLoading?: boolean;
  errorMessage?: string | null;
}

const markdownComponents = {
  p: ({ children }: { children: ReactNode }) => (
    <p className="mb-3 text-base leading-relaxed text-slate-800 last:mb-0">{children}</p>
  ),
  strong: ({ children }: { children: ReactNode }) => (
    <strong className="font-semibold text-slate-900">{children}</strong>
  ),
  ul: ({ children }: { children: ReactNode }) => (
    <ul className="mb-3 list-disc pl-5 text-slate-800 last:mb-0">{children}</ul>
  ),
  ol: ({ children }: { children: ReactNode }) => (
    <ol className="mb-3 list-decimal pl-5 text-slate-800 last:mb-0">{children}</ol>
  ),
  code: ({ children }: { children: ReactNode }) => (
    <code className="rounded bg-slate-100 px-1.5 py-0.5 text-sm text-slate-900">{children}</code>
  ),
  pre: ({ children }: { children: ReactNode }) => (
    <pre className="mb-3 overflow-x-auto rounded-xl bg-slate-900/90 p-4 text-sm text-slate-100 shadow-inner last:mb-0">
      {children}
    </pre>
  ),
  a: ({ href, children }: { href?: string; children: ReactNode }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer"
      className="text-slate-900 underline decoration-slate-300 underline-offset-4 hover:text-slate-700"
    >
      {children}
    </a>
  ),
  blockquote: ({ children }: { children: ReactNode }) => (
    <blockquote className="mb-3 border-l-4 border-slate-200 pl-4 text-slate-600">{children}</blockquote>
  ),
};

const QueryResult = ({ result, isLoading = false, errorMessage }: QueryResultProps) => {
  const [copied, setCopied] = useState(false);

  const confidenceLabel = useMemo(() => {
    if (!result) return null;
    const rawValue = typeof result.confidence === 'number' ? result.confidence : undefined;
    if (rawValue == null) return null;
    const normalized = rawValue <= 1 ? rawValue * 100 : rawValue;
    const safeValue = Math.max(0, Math.min(100, normalized));
    return `${safeValue.toFixed(0)}% 置信度`;
  }, [result]);

  const verificationUrl = result?.verification_report_url;

  const handleCopy = async () => {
    if (!result?.answer) return;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(result.answer);
      } else {
        const textarea = document.createElement('textarea');
        textarea.value = result.answer;
        textarea.style.position = 'fixed';
        textarea.style.left = '-9999px';
        document.body.appendChild(textarea);
        textarea.select();
        document.execCommand('copy');
        document.body.removeChild(textarea);
      }
      setCopied(true);
      setTimeout(() => setCopied(false), 2200);
    } catch (error) {
      console.error('复制失败', error);
    }
  };

  const renderContent = () => {
    if (isLoading) {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-slate-500">
          <Spinner label="查询执行中" />
          <p className="text-sm">正在推理解答，请稍候...</p>
        </div>
      );
    }

    if (errorMessage) {
      return (
        <div className="rounded-2xl border border-red-200 bg-red-50/80 p-4 text-sm text-red-600">
          {errorMessage}
        </div>
      );
    }

    if (!result) {
      return (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center text-slate-500">
          <FileText className="h-10 w-10 text-slate-300" />
          <div>
            <p className="text-base font-medium text-slate-700">暂无查询结果</p>
            <p className="text-sm">提交查询后将在此展示由 AI 生成的答案与引用来源。</p>
          </div>
        </div>
      );
    }

    return (
      <>
        <div className="overflow-y-auto pr-2 text-slate-800">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={markdownComponents}
            className="flex flex-col gap-2"
          >
            {result.answer || '（暂无回答内容）'}
          </ReactMarkdown>
        </div>
        {Array.isArray(result.sources) && result.sources.length > 0 && (
          <div className="rounded-2xl border border-slate-100 bg-slate-50/80 p-4">
            <p className="text-sm font-semibold text-slate-600">引用来源</p>
            <ul className="mt-2 space-y-2 text-sm text-slate-600">
              {result.sources.map((source) => (
                <li key={source} className="flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-500" />
                  <span className="truncate">{source}</span>
                </li>
              ))}
            </ul>
          </div>
        )}
        <div className="flex flex-wrap gap-3 pt-2">
          <Button
            variant="outline"
            type="button"
            className="inline-flex items-center gap-2"
            onClick={handleCopy}
            disabled={!result.answer}
          >
            {copied ? <Check className="h-4 w-4" /> : <Clipboard className="h-4 w-4" />}
            {copied ? '已复制' : '复制答案'}
          </Button>
          <Button
            type="button"
            className="inline-flex items-center gap-2"
            disabled={!verificationUrl}
            onClick={() => {
              if (verificationUrl) {
                window.open(verificationUrl, '_blank', 'noreferrer');
              }
            }}
          >
            <ExternalLink className="h-4 w-4" />
            查看验证报告
          </Button>
          {result.trace_id && (
            <Link
              to={`/visualization/trace/${result.trace_id}`}
              className="inline-flex items-center gap-2 rounded-md border border-transparent px-3 py-2 text-sm font-medium text-slate-600 underline decoration-dashed hover:text-slate-900"
            >
              <GitBranch className="h-4 w-4" />
              查看推理轨迹
            </Link>
          )}
        </div>
      </>
    );
  };

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="flex flex-col gap-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <CardTitle className="text-xl">查询结果</CardTitle>
            <CardDescription>渲染 Markdown 内容，追踪置信度和链路信息</CardDescription>
          </div>
          {confidenceLabel && (
            <div className="inline-flex items-center gap-2 rounded-full bg-emerald-50 px-4 py-1 text-sm font-medium text-emerald-700">
              <LineChart className="h-4 w-4" />
              {confidenceLabel}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col gap-4">
        {renderContent()}
      </CardContent>
    </Card>
  );
};

export default QueryResult;
