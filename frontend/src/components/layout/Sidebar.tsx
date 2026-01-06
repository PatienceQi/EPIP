import {
  Activity,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Network,
  Search,
  Settings,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { cn } from '@/lib/cn';

import packageJson from '../../../package.json';

const NAV_ITEMS = [
  {
    label: '仪表板',
    to: '/',
    icon: LayoutDashboard,
    exact: true,
  },
  {
    label: '查询中心',
    to: '/query',
    icon: Search,
  },
  {
    label: '可视化',
    to: '/visualization',
    icon: Network,
  },
  {
    label: '管理控制台',
    to: '/admin',
    icon: Settings,
  },
  {
    label: '监控中心',
    to: '/monitor',
    icon: Activity,
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

const Sidebar = ({ collapsed, onToggle }: SidebarProps) => {
  return (
    <aside
      className={cn(
        'fixed left-0 top-16 hidden h-[calc(100vh-4rem)] flex-col border-r border-slate-200 bg-sidebar text-slate-600 shadow-sm transition-all duration-200 md:flex',
        collapsed ? 'w-16' : 'w-60'
      )}
    >
      <div className="flex items-center justify-between px-3 py-4">
        <span className={cn('text-xs font-semibold uppercase tracking-wide text-slate-500', collapsed && 'sr-only')}>
          导航
        </span>
        <button
          type="button"
          aria-label={collapsed ? '展开侧边栏' : '折叠侧边栏'}
          onClick={onToggle}
          className="inline-flex h-8 w-8 items-center justify-center rounded-md border border-transparent text-slate-500 transition hover:border-slate-300 hover:bg-white hover:text-primary focus:outline-none focus:ring-2 focus:ring-primary"
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-2" aria-label="主导航">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.exact}
            className={({ isActive }) =>
              cn(
                'group flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-slate-600 transition-colors hover:bg-white hover:text-primary',
                collapsed && 'justify-center px-0',
                isActive && 'bg-white text-primary shadow-sm'
              )
            }
          >
            <item.icon className="h-5 w-5" />
            <span className={cn('whitespace-nowrap', collapsed && 'sr-only')}>{item.label}</span>
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-slate-200 px-3 py-3 text-xs text-slate-500">
        <div className={cn('flex items-center gap-2', collapsed && 'flex-col gap-1 text-center')}>
          <span className={cn(collapsed && 'sr-only')}>版本</span>
          <span className="font-semibold text-slate-700">v{packageJson.version}</span>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
