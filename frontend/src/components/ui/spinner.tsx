import * as React from 'react';

import { cn } from '@/lib/cn';

const spinnerSizes = {
  sm: 'h-4 w-4',
  md: 'h-6 w-6',
  lg: 'h-8 w-8',
};

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: keyof typeof spinnerSizes;
  label?: string;
}

export const Spinner = ({
  className,
  size = 'md',
  label = 'Loading...',
  ...props
}: SpinnerProps) => (
  <div
    role="status"
    aria-live="polite"
    className={cn('inline-flex items-center justify-center', className)}
    {...props}
  >
    <span
      className={cn(
        'inline-flex rounded-full border-2 border-slate-200 border-t-slate-900 animate-spin',
        spinnerSizes[size]
      )}
    />
    <span className="sr-only">{label}</span>
  </div>
);
