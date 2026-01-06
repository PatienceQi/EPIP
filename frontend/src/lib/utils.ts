export function formatDate(
  value: Date | string | number,
  options?: Intl.DateTimeFormatOptions,
  locale: string = 'en-US'
): string {
  const date = value instanceof Date ? value : new Date(value);

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const defaultOptions: Intl.DateTimeFormatOptions = options?.dateStyle || options?.timeStyle
    ? options
    : {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        ...options,
      };

  const formatter = new Intl.DateTimeFormat(locale, defaultOptions);

  return formatter.format(date);
}

export function formatNumber(
  value: number | string,
  options?: Intl.NumberFormatOptions,
  locale: string = 'en-US'
): string {
  const numericValue = typeof value === 'number' ? value : Number(value);

  if (!Number.isFinite(numericValue)) {
    return '';
  }

  const formatter = new Intl.NumberFormat(locale, {
    maximumFractionDigits: 2,
    ...options,
  });

  return formatter.format(numericValue);
}

export function truncate(value: string, maxLength = 80, suffix = '...'): string {
  if (value.length <= maxLength) {
    return value;
  }

  if (maxLength <= suffix.length) {
    return value.slice(0, maxLength);
  }

  return `${value.slice(0, maxLength - suffix.length)}${suffix}`;
}
