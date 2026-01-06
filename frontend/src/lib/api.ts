import axios, { AxiosError, AxiosRequestConfig, AxiosResponse } from 'axios';

type TenantIdResolver = () => string | null | undefined;

let tenantIdResolver: TenantIdResolver | null = null;

export const registerTenantResolver = (resolver: TenantIdResolver) => {
  tenantIdResolver = resolver;
};

export const api = axios.create({
  baseURL: '',
  timeout: 15000,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const tenantId = tenantIdResolver?.();
  if (tenantId) {
    config.headers = config.headers ?? {};
    config.headers['X-Tenant-ID'] = tenantId;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ message?: string }>) => {
    const message =
      (typeof error.response?.data === 'object' && error.response?.data?.message) ||
      error.message ||
      'Request failed';

    const formattedError = new Error(message);
    (formattedError as Error & { status?: number }).status = error.response?.status;
    return Promise.reject(formattedError);
  }
);

const unwrap = <T>(promise: Promise<AxiosResponse<T>>) => promise.then((response) => response.data);

export const get = <T>(url: string, config?: AxiosRequestConfig) => unwrap<T>(api.get<T>(url, config));
export const post = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  unwrap<T>(api.post<T>(url, data, config));
export const put = <T>(url: string, data?: unknown, config?: AxiosRequestConfig) =>
  unwrap<T>(api.put<T>(url, data, config));
export const del = <T>(url: string, config?: AxiosRequestConfig) => unwrap<T>(api.delete<T>(url, config));

export type ApiGet = typeof get;
export type ApiPost = typeof post;
