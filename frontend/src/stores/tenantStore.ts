import { create } from 'zustand';

import { get, registerTenantResolver } from '@/lib/api';
import { Tenant } from '@/types/api';

export interface TenantStoreState {
  currentTenantId: string | null;
  tenants: Tenant[];
  setCurrentTenant: (tenantId: string | null) => void;
  fetchTenants: () => Promise<Tenant[]>;
}

export const useTenantStore = create<TenantStoreState>((set) => ({
  currentTenantId: null,
  tenants: [],
  setCurrentTenant: (tenantId) => {
    set({ currentTenantId: tenantId });
  },
  fetchTenants: async () => {
    const tenants = await get<Tenant[]>('/api/tenants');

    set((state) => ({
      tenants,
      currentTenantId: state.currentTenantId ?? tenants[0]?.tenant_id ?? null,
    }));

    return tenants;
  },
}));

registerTenantResolver(() => useTenantStore.getState().currentTenantId ?? undefined);
