import { ChangeEvent } from 'react';
import { RefreshCcw } from 'lucide-react';

import { useTenants } from '@/hooks/useApi';
import { cn } from '@/lib/cn';

import Breadcrumbs from './Breadcrumbs';

interface HeaderProps {
  sidebarCollapsed: boolean;
}

const Header = ({ sidebarCollapsed }: HeaderProps) => {
  const {
    data: tenants = [],
    currentTenantId,
    setCurrentTenant,
    refetch,
    isFetching,
  } = useTenants();

  const handleTenantChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setCurrentTenant(event.target.value || null);
  };

  const handleRefresh = () => {
    void refetch();
  };

  const hasTenants = tenants.length > 0;

  return (
    <header
      className={cn(
        'fixed inset-x-0 top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur transition-[padding] duration-200',
        sidebarCollapsed ? 'md:pl-16' : 'md:pl-60'
      )}
    >
      <div className="flex h-16 w-full flex-wrap items-center gap-4 px-4 md:px-6">
        <div className="flex items-center gap-2">
          <span className="text-lg font-semibold text-primary">EPIP</span>
          <span className="hidden text-sm text-slate-500 sm:inline">图谱智能平台</span>
        </div>
        <div className="flex flex-1 justify-center">
          <Breadcrumbs />
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-sm text-slate-500">
            <span className="hidden text-xs font-medium uppercase tracking-wide sm:inline">
              租户
            </span>
            <select
              value={currentTenantId ?? ''}
              onChange={handleTenantChange}
              className="min-w-[160px] rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 shadow-sm focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {!hasTenants && <option value="">暂无租户</option>}
              {hasTenants && !currentTenantId && <option value="">选择租户</option>}
              {tenants.map((tenant) => (
                <option key={tenant.tenant_id} value={tenant.tenant_id}>
                  {tenant.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            onClick={handleRefresh}
            className="inline-flex h-10 items-center justify-center rounded-md border border-slate-200 px-3 text-sm font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-primary disabled:opacity-50"
            aria-label="刷新租户"
            disabled={isFetching}
          >
            <RefreshCcw className={cn('h-4 w-4', isFetching && 'animate-spin')} />
          </button>
        </div>
      </div>
    </header>
  );
};

export default Header;
