import { useState } from 'react';

import HealthStatus from './HealthStatus';
import Metrics from './Metrics';
import { cn } from '@/lib/cn';

const REFRESH_INTERVAL = 30_000;

const Monitor = () => {
  const [autoRefresh, setAutoRefresh] = useState(true);

  return (
    <section className="space-y-8">
      <header className="flex flex-col gap-4 rounded-3xl border border-slate-100 bg-gradient-to-br from-white to-slate-50/80 p-6 shadow-sm lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-sm uppercase tracking-wide text-indigo-500">EPIP Monitor</p>
          <h1 className="mt-1 text-3xl font-semibold text-slate-900">监控中心</h1>
          <p className="mt-2 text-base text-slate-500">
            集中掌握系统健康、依赖服务与性能指标，支持自动与手动刷新的混合监控。
          </p>
        </div>
        <div className="flex items-center gap-4 rounded-2xl border border-slate-200 bg-white/80 p-4">
          <div>
            <p className="text-sm font-medium text-slate-900">自动刷新</p>
            <p className="text-xs text-slate-500">每 30 秒同步监控数据，可随时手动刷新</p>
          </div>
          <button
            type="button"
            role="switch"
            aria-checked={autoRefresh}
            onClick={() => setAutoRefresh((value) => !value)}
            className={cn(
              'relative inline-flex h-9 w-16 flex-shrink-0 items-center rounded-full transition',
              autoRefresh ? 'bg-emerald-500' : 'bg-slate-300'
            )}
          >
            <span className="sr-only">切换自动刷新</span>
            <span
              className={cn(
                'inline-block h-7 w-7 transform rounded-full bg-white shadow transition',
                autoRefresh ? 'translate-x-8' : 'translate-x-1'
              )}
            />
          </button>
        </div>
      </header>

      <HealthStatus autoRefresh={autoRefresh} refreshInterval={REFRESH_INTERVAL} />
      <Metrics autoRefresh={autoRefresh} refreshInterval={REFRESH_INTERVAL} />
    </section>
  );
};

export default Monitor;
