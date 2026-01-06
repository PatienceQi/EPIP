import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useHealth, useCacheStats } from '../useApi'
import * as api from '@/lib/api'

vi.mock('@/lib/api', () => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
  registerTenantResolver: vi.fn(),
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  )
}

describe('useHealth', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches health data successfully', async () => {
    const mockData = { status: 'healthy', services: { neo4j: 'up', redis: 'up' } }
    vi.mocked(api.get).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useHealth(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockData)
    expect(api.get).toHaveBeenCalledWith('/api/health')
  })

  it('handles error state', async () => {
    vi.mocked(api.get).mockRejectedValueOnce(new Error('Network error'))

    const { result } = renderHook(() => useHealth(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(result.current.error?.message).toBe('Network error')
  })
})

describe('useCacheStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('fetches cache stats successfully', async () => {
    const mockData = { hits: 100, misses: 20, size: 50 }
    vi.mocked(api.get).mockResolvedValueOnce(mockData)

    const { result } = renderHook(() => useCacheStats(), { wrapper: createWrapper() })

    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(result.current.data).toEqual(mockData)
    expect(api.get).toHaveBeenCalledWith('/api/cache/stats')
  })
})
