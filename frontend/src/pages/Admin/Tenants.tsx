import { FormEvent, useMemo, useState } from 'react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Modal } from '@/components/ui/modal';
import { Spinner } from '@/components/ui/spinner';
import {
  useCreateTenant,
  useDeleteTenant,
  useTenants,
  useUpdateTenant,
} from '@/hooks/useApi';
import type { Tenant } from '@/types/api';
import { formatDate as formatDateUtil } from '@/lib/utils';

type TenantFormState = {
  tenant_id: string;
  name: string;
  status: string;
  configText: string;
};

const defaultFormState: TenantFormState = {
  tenant_id: '',
  name: '',
  status: 'ACTIVE',
  configText: '{}',
};

const renderStatusBadge = (status: string) => {
  const normalized = status?.toUpperCase() ?? 'UNKNOWN';
  const variants: Record<string, { label: string; className: string }> = {
    ACTIVE: { label: '启用', className: 'bg-green-100 text-green-700' },
    SUSPENDED: { label: '停用', className: 'bg-amber-100 text-amber-700' },
    INACTIVE: { label: '未激活', className: 'bg-slate-100 text-slate-600' },
  };
  const config = variants[normalized] ?? { label: normalized, className: 'bg-slate-100 text-slate-600' };
  return (
    <Badge variant="secondary" className={config.className}>
      {config.label}
    </Badge>
  );
};

const formatDate = (value?: string) => {
  if (!value) return '--';
  return formatDateUtil(value, { dateStyle: 'medium', timeStyle: 'short' }, 'zh-CN');
};

const Tenants = () => {
  const { data: tenants = [], isLoading, isFetching, refetch } = useTenants();
  const createTenant = useCreateTenant();
  const updateTenant = useUpdateTenant();
  const deleteTenant = useDeleteTenant();

  const [searchTerm, setSearchTerm] = useState('');
  const [formMode, setFormMode] = useState<'create' | 'edit' | null>(null);
  const [formState, setFormState] = useState<TenantFormState>(defaultFormState);
  const [configError, setConfigError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<Tenant | null>(null);

  const filteredTenants = useMemo(() => {
    if (!searchTerm) return tenants;
    return tenants.filter((tenant) => {
      const keyword = searchTerm.toLowerCase();
      return (
        tenant.tenant_id.toLowerCase().includes(keyword) ||
        tenant.name?.toLowerCase().includes(keyword) ||
        tenant.status?.toLowerCase().includes(keyword)
      );
    });
  }, [searchTerm, tenants]);

  const handleOpenCreate = () => {
    setFormMode('create');
    setFormState(defaultFormState);
    setConfigError(null);
  };

  const handleOpenEdit = (tenant: Tenant) => {
    setFormMode('edit');
    setFormState({
      tenant_id: tenant.tenant_id,
      name: tenant.name,
      status: tenant.status,
      configText: JSON.stringify(tenant.config ?? {}, null, 2),
    });
    setConfigError(null);
  };

  const handleFormSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (!formState.tenant_id || !formState.name) {
      setConfigError('租户 ID 与名称均为必填');
      return;
    }
    let parsedConfig: Record<string, unknown> = {};
    const trimmed = formState.configText?.trim();
    if (trimmed && trimmed !== '{}') {
      try {
        parsedConfig = JSON.parse(trimmed);
      } catch {
        setConfigError('配置必须是合法的 JSON');
        return;
      }
    }
    const payload = {
      tenant_id: formState.tenant_id.trim(),
      name: formState.name.trim(),
      status: formState.status,
      config: parsedConfig,
    };
    try {
      if (formMode === 'edit') {
        await updateTenant.mutateAsync(payload);
      } else {
        await createTenant.mutateAsync(payload);
      }
      setFormMode(null);
      setFormState(defaultFormState);
    } catch (error) {
      if (error instanceof Error) {
        setConfigError(error.message);
      }
    }
  };

  const handleToggleStatus = async (tenant: Tenant) => {
    const nextStatus = tenant.status === 'ACTIVE' ? 'SUSPENDED' : 'ACTIVE';
    try {
      await updateTenant.mutateAsync({ tenant_id: tenant.tenant_id, status: nextStatus });
    } catch {
      // no-op, error surfaced via toast boundary or global handler
    }
  };

  const confirmDelete = async () => {
    if (!deleteTarget) return;
    try {
      await deleteTenant.mutateAsync(deleteTarget.tenant_id);
      setDeleteTarget(null);
    } catch {
      // handled by global boundary
    }
  };

  const closeModal = () => {
    setFormMode(null);
    setConfigError(null);
    setFormState(defaultFormState);
  };

  return (
    <section className="space-y-6">
      <header>
        <h1 className="text-3xl font-semibold text-slate-900">租户管理</h1>
        <p className="mt-2 text-base text-slate-500">管理多租户配置、状态与生命周期。</p>
      </header>

      <Card className="border-slate-100 shadow-none">
        <CardContent className="flex flex-col gap-4 py-6 md:flex-row md:items-center md:justify-between">
          <div className="flex w-full flex-1 items-center gap-3">
            <div className="w-full md:max-w-sm">
              <Input
                placeholder="搜索租户 ID / 名称 / 状态"
                value={searchTerm}
                onChange={(event) => setSearchTerm(event.target.value)}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button variant="outline" onClick={() => refetch()} disabled={isFetching}>
              {isFetching ? '刷新中...' : '刷新列表'}
            </Button>
            <Button onClick={handleOpenCreate}>新建租户</Button>
          </div>
        </CardContent>
      </Card>

      <Card className="border-slate-100 shadow-none">
        <CardHeader>
          <CardTitle className="text-base font-semibold text-slate-900">租户列表</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex min-h-[200px] items-center justify-center p-6">
              <Spinner label="加载租户列表" />
            </div>
          ) : filteredTenants.length === 0 ? (
            <div className="p-6 text-center text-sm text-slate-500">暂无符合条件的租户。</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full text-left text-sm text-slate-700">
                <thead>
                  <tr className="border-b border-slate-100 bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-6 py-3 font-medium">租户 ID</th>
                    <th className="px-6 py-3 font-medium">名称</th>
                    <th className="px-6 py-3 font-medium">状态</th>
                    <th className="px-6 py-3 font-medium">创建时间</th>
                    <th className="px-6 py-3 font-medium text-right">操作</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTenants.map((tenant) => (
                    <tr key={tenant.tenant_id} className="border-b border-slate-100 hover:bg-slate-50/80">
                      <td className="px-6 py-4 font-mono text-xs text-slate-900 md:text-sm">
                        {tenant.tenant_id}
                      </td>
                      <td className="px-6 py-4">{tenant.name}</td>
                      <td className="px-6 py-4">{renderStatusBadge(tenant.status)}</td>
                      <td className="px-6 py-4 text-slate-500">{formatDate(tenant.created_at)}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center justify-end gap-2">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleToggleStatus(tenant)}
                            disabled={updateTenant.isPending}
                          >
                            切换状态
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => handleOpenEdit(tenant)}>
                            编辑
                          </Button>
                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => setDeleteTarget(tenant)}
                            disabled={deleteTenant.isPending}
                          >
                            删除
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Modal
        open={Boolean(formMode)}
        title={formMode === 'edit' ? '编辑租户' : '新建租户'}
        onClose={closeModal}
        footer={
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={closeModal}>
              取消
            </Button>
            <Button
              type="submit"
              form="tenant-form"
              disabled={createTenant.isPending || updateTenant.isPending}
            >
              保存
            </Button>
          </div>
        }
      >
        <form id="tenant-form" className="space-y-4" onSubmit={handleFormSubmit}>
          <div>
            <label className="text-sm font-medium text-slate-700">租户 ID</label>
            <Input
              className="mt-1"
              placeholder="如 acme-prod"
              value={formState.tenant_id}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, tenant_id: event.target.value }))
              }
              disabled={formMode === 'edit'}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">名称</label>
            <Input
              className="mt-1"
              placeholder="租户展示名称"
              value={formState.name}
              onChange={(event) => setFormState((prev) => ({ ...prev, name: event.target.value }))}
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">状态</label>
            <select
              className="mt-1 h-10 w-full rounded-md border border-slate-200 px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
              value={formState.status}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, status: event.target.value }))
              }
            >
              <option value="ACTIVE">ACTIVE</option>
              <option value="SUSPENDED">SUSPENDED</option>
              <option value="INACTIVE">INACTIVE</option>
            </select>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">配置 JSON</label>
            <textarea
              className="mt-1 h-32 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm font-mono text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-slate-900"
              value={formState.configText}
              onChange={(event) =>
                setFormState((prev) => ({ ...prev, configText: event.target.value }))
              }
            />
            <p className="mt-1 text-xs text-slate-400">用于指定 Neo4j 数据库、功能开关等。</p>
          </div>
          {configError && <p className="text-sm text-red-500">{configError}</p>}
          <button type="submit" className="hidden" />
        </form>
      </Modal>

      <Modal
        open={Boolean(deleteTarget)}
        title="删除租户"
        onClose={() => setDeleteTarget(null)}
        footer={
          <div className="flex justify-end gap-3">
            <Button type="button" variant="outline" onClick={() => setDeleteTarget(null)}>
              取消
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={deleteTenant.isPending}
            >
              确认删除
            </Button>
          </div>
        }
      >
        <p className="text-sm text-slate-600">
          即将删除租户{' '}
          <span className="font-semibold text-slate-900">{deleteTarget?.tenant_id}</span>，该操作不可
          撤销，确认继续？
        </p>
      </Modal>
    </section>
  );
};

export default Tenants;
