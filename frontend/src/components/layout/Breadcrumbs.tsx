import { Fragment } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ChevronRight } from 'lucide-react';

import { cn } from '@/lib/cn';

const BREADCRUMB_LABELS: Record<string, string> = {
  '/': '仪表板',
  '/query': '查询中心',
  '/visualization': '可视化',
  '/visualization/trace': '追踪详情',
  '/admin': '管理控制台',
  '/admin/tenants': '租户管理',
  '/admin/cache': '缓存管理',
  '/monitor': '监控中心',
};

interface BreadcrumbsProps {
  className?: string;
}

interface Crumb {
  pathname: string;
  label: string;
  isLast: boolean;
}

const getLabel = (pathname: string, fallback: string) => {
  return BREADCRUMB_LABELS[pathname] ?? fallback;
};

const useBreadcrumbs = (): Crumb[] => {
  const location = useLocation();
  const segments = location.pathname === '/' ? [] : location.pathname.split('/').filter(Boolean);

  const crumbs: Omit<Crumb, 'isLast'>[] = [
    {
      pathname: '/',
      label: getLabel('/', '首页'),
    },
  ];

  if (segments.length > 0) {
    let pathAccumulator = '';

    segments.forEach((segment) => {
      pathAccumulator += `/${segment}`;
      const decodedSegment = decodeURIComponent(segment);

      crumbs.push({
        pathname: pathAccumulator,
        label: getLabel(pathAccumulator, decodedSegment),
      });
    });
  }

  return crumbs.map((crumb, index) => ({
    ...crumb,
    isLast: index === crumbs.length - 1,
  }));
};

const Breadcrumbs = ({ className }: BreadcrumbsProps) => {
  const crumbs = useBreadcrumbs();

  return (
    <nav
      aria-label="面包屑导航"
      className={cn('flex items-center text-sm text-slate-500', className)}
    >
      {crumbs.map((crumb, index) => (
        <Fragment key={crumb.pathname || index}>
          {index > 0 && <ChevronRight className="mx-2 h-4 w-4 text-slate-400" />}
          {crumb.isLast ? (
            <span className="font-medium text-slate-900">{crumb.label}</span>
          ) : (
            <Link
              to={crumb.pathname}
              className="transition-colors hover:text-slate-900"
            >
              {crumb.label}
            </Link>
          )}
        </Fragment>
      ))}
    </nav>
  );
};

export default Breadcrumbs;
