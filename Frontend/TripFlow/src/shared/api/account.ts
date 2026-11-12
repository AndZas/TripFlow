import { api } from './client'

export type Account = { id: string; email: string }

export const getAccount = (signal: AbortSignal) => api<Account>('/auth/me', { signal })

export function returnPath(state: { from?: unknown } | null) {
  const path = state?.from
  return typeof path === 'string' && /^\/(?:dashboards(?:\/[\w-]+)?|join\/[a-fA-F0-9]{64})$/.test(path)
    ? path : '/dashboards'
}
