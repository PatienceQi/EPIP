import * as React from 'react';

import { cn } from '@/lib/cn';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {}

export const Skeleton = ({ className, ...props }: SkeletonProps) => (
  <div className={cn('animate-pulse rounded-md bg-slate-100', className)} {...props} />
);
