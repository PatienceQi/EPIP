import { useState } from 'react';
import { Outlet } from 'react-router-dom';

import { cn } from '@/lib/cn';

import Header from './Header';
import Sidebar from './Sidebar';

const AppLayout = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const toggleSidebar = () => setSidebarCollapsed((prev) => !prev);

  return (
    <div className="min-h-screen bg-surface text-slate-900">
      <Header sidebarCollapsed={sidebarCollapsed} />
      <Sidebar collapsed={sidebarCollapsed} onToggle={toggleSidebar} />
      <div
        className={cn(
          'pt-16 transition-all duration-200',
          sidebarCollapsed ? 'md:ml-16' : 'md:ml-60'
        )}
      >
        <main className="flex min-h-[calc(100vh-4rem)] flex-col px-4 py-6 md:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
