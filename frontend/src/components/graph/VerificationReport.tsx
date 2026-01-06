import { useMemo } from 'react';

import { Badge } from '@/components/ui/badge';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/cn';

type VerificationStatus = 'verified' | 'unverified' | 'conflicting';

export interface VerificationEvidence {
  label: string;
  url: string;
  source?: string;
}

export interface VerificationFact {
  id: string;
  statement: string;
  status: VerificationStatus;
  evidence?: VerificationEvidence[];
  notes?: string;
}

interface VerificationReportProps {
  facts: VerificationFact[];
  overallConfidence: number;
}

const STATUS_COPY: Record<
  VerificationStatus,
  { label: string; badgeVariant: 'default' | 'secondary' | 'destructive'; indicator: string }
> = {
  verified: { label: '已验证', badgeVariant: 'default', indicator: 'bg-emerald-500' },
  unverified: { label: '待验证', badgeVariant: 'secondary', indicator: 'bg-slate-400' },
  conflicting: { label: '存在冲突', badgeVariant: 'destructive', indicator: 'bg-amber-500' },
};

const clampPercent = (value: number): number => {
  if (Number.isNaN(value)) return 0;
  const normalized = value <= 1 ? value * 100 : value;
  return Math.min(100, Math.max(0, normalized));
};

export const VerificationReport = ({ facts, overallConfidence }: VerificationReportProps) => {
  const confidencePercent = clampPercent(overallConfidence);

  const statusBreakdown = useMemo(
    () =>
      facts.reduce(
        (acc, fact) => {
          acc[fact.status] += 1;
          return acc;
        },
        { verified: 0, unverified: 0, conflicting: 0 }
      ),
    [facts]
  );

  return (
    <Card className="h-full w-full bg-white">
      <CardHeader>
        <CardTitle>验证报告</CardTitle>
        <CardDescription>事实核查状态与证据视图</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex flex-wrap gap-3">
          {(Object.keys(statusBreakdown) as VerificationStatus[]).map((status) => (
            <Badge
              key={status}
              variant={STATUS_COPY[status].badgeVariant}
              className="flex items-center gap-2 rounded-full px-3 py-1 text-sm"
            >
              <span className={cn('h-2 w-2 rounded-full', STATUS_COPY[status].indicator)} />
              {STATUS_COPY[status].label} · {statusBreakdown[status]}
            </Badge>
          ))}
        </div>

        <div className="space-y-4">
          {facts.length === 0 ? (
            <p className="text-sm text-slate-500">暂无事实记录。</p>
          ) : (
            facts.map((fact) => (
              <div
                key={fact.id}
                className="rounded-2xl border border-slate-200 bg-slate-50 p-4 transition hover:border-slate-300"
              >
                <div className="flex flex-wrap items-center gap-3">
                  <p className="flex-1 text-base font-semibold text-slate-900">{fact.statement}</p>
                  <Badge variant={STATUS_COPY[fact.status].badgeVariant}>
                    {STATUS_COPY[fact.status].label}
                  </Badge>
                </div>
                {fact.notes ? (
                  <p className="mt-2 text-sm text-slate-600">{fact.notes}</p>
                ) : null}

                {fact.evidence && fact.evidence.length > 0 ? (
                  <div className="mt-3 space-y-2 text-sm text-slate-500">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
                      证据来源
                    </p>
                    <ul className="space-y-2">
                      {fact.evidence.map((item) => (
                        <li
                          key={`${fact.id}-${item.url}`}
                          className="flex flex-wrap items-center gap-2 border-b border-dashed border-slate-200 pb-2 last:border-none last:pb-0"
                        >
                          <a
                            href={item.url}
                            className="text-blue-600 hover:text-blue-700"
                            target="_blank"
                            rel="noreferrer"
                          >
                            {item.label}
                          </a>
                          {item.source ? (
                            <span className="text-xs text-slate-500">({item.source})</span>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </CardContent>
      <CardFooter className="flex flex-col gap-3">
        <div className="flex w-full items-center justify-between text-sm font-medium text-slate-700">
          <span>整体可信度</span>
          <span>{confidencePercent.toFixed(0)}%</span>
        </div>
        <div className="h-2 w-full rounded-full bg-slate-100">
          <div
            className="h-2 rounded-full bg-emerald-500 transition-all"
            style={{ width: `${confidencePercent}%` }}
            role="progressbar"
            aria-valuenow={confidencePercent}
            aria-valuemin={0}
            aria-valuemax={100}
          />
        </div>
      </CardFooter>
    </Card>
  );
};

export default VerificationReport;
