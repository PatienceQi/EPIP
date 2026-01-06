import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, it, expect, vi } from 'vitest'
import Dashboard from '../Dashboard'

vi.mock('../Dashboard/StatCards', () => ({
  default: () => <div data-testid="stat-cards">StatCards</div>,
}))

vi.mock('../Dashboard/RecentQueries', () => ({
  default: ({ className }: { className?: string }) => (
    <div data-testid="recent-queries" className={className}>RecentQueries</div>
  ),
}))

vi.mock('../Dashboard/SystemHealth', () => ({
  default: () => <div data-testid="system-health">SystemHealth</div>,
}))

const createWrapper = () => {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{children}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('Dashboard', () => {
  it('renders page title', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('系统概览')).toBeInTheDocument()
  })

  it('renders EPIP label', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('EPIP')).toBeInTheDocument()
  })

  it('renders description', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('掌握平台运行状态、近期查询与关键入口。')).toBeInTheDocument()
  })

  it('renders StatCards component', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByTestId('stat-cards')).toBeInTheDocument()
  })

  it('renders RecentQueries component', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByTestId('recent-queries')).toBeInTheDocument()
  })

  it('renders SystemHealth component', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByTestId('system-health')).toBeInTheDocument()
  })

  it('renders quick entry links', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('查询中心')).toBeInTheDocument()
    expect(screen.getByText('可视化')).toBeInTheDocument()
    expect(screen.getByText('管理控制台')).toBeInTheDocument()
  })

  it('renders quick entry section title', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('快速入口')).toBeInTheDocument()
  })

  it('has correct link destinations', () => {
    render(<Dashboard />, { wrapper: createWrapper() })
    expect(screen.getByText('查询中心').closest('a')).toHaveAttribute('href', '/query')
    expect(screen.getByText('可视化').closest('a')).toHaveAttribute('href', '/visualization')
    expect(screen.getByText('管理控制台').closest('a')).toHaveAttribute('href', '/admin')
  })
})
