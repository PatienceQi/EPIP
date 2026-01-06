import { describe, it, expect, beforeEach, vi } from 'vitest'
import { act } from '@testing-library/react'
import { useTenantStore } from '../tenantStore'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  get: vi.fn(),
  registerTenantResolver: vi.fn(),
}))

describe('tenantStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useTenantStore.setState({ currentTenantId: null, tenants: [] })
    })
  })

  it('has initial state', () => {
    const state = useTenantStore.getState()
    expect(state.currentTenantId).toBeNull()
    expect(state.tenants).toEqual([])
  })

  it('sets current tenant', () => {
    act(() => {
      useTenantStore.getState().setCurrentTenant('tenant-1')
    })
    expect(useTenantStore.getState().currentTenantId).toBe('tenant-1')
  })

  it('sets current tenant to null', () => {
    act(() => {
      useTenantStore.getState().setCurrentTenant('tenant-1')
      useTenantStore.getState().setCurrentTenant(null)
    })
    expect(useTenantStore.getState().currentTenantId).toBeNull()
  })

  it('fetches tenants and sets first as current', async () => {
    const mockTenants = [
      { tenant_id: 'tenant-1', name: 'Tenant 1' },
      { tenant_id: 'tenant-2', name: 'Tenant 2' },
    ]
    vi.mocked(api.get).mockResolvedValueOnce(mockTenants)

    await act(async () => {
      await useTenantStore.getState().fetchTenants()
    })

    const state = useTenantStore.getState()
    expect(state.tenants).toEqual(mockTenants)
    expect(state.currentTenantId).toBe('tenant-1')
  })

  it('keeps current tenant if already set', async () => {
    const mockTenants = [
      { tenant_id: 'tenant-1', name: 'Tenant 1' },
      { tenant_id: 'tenant-2', name: 'Tenant 2' },
    ]
    vi.mocked(api.get).mockResolvedValueOnce(mockTenants)

    act(() => {
      useTenantStore.setState({ currentTenantId: 'tenant-2' })
    })

    await act(async () => {
      await useTenantStore.getState().fetchTenants()
    })

    expect(useTenantStore.getState().currentTenantId).toBe('tenant-2')
  })

  it('handles empty tenants list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce([])

    await act(async () => {
      await useTenantStore.getState().fetchTenants()
    })

    const state = useTenantStore.getState()
    expect(state.tenants).toEqual([])
    expect(state.currentTenantId).toBeNull()
  })
})
