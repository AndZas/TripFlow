import { api } from '../../../shared/api/client'
import type { Card, DashboardDetails, Destination, TripInput } from '../model/types'

const dashboardPath = (id: string) => '/dashboards/' + encodeURIComponent(id)
const cardPath = (dashboardId: string, cardId: string) =>
  dashboardPath(dashboardId) + '/cards/' + encodeURIComponent(cardId)

export const getDestinations = (signal: AbortSignal) => api<Destination[]>('/destinations', { signal })
export const getDashboard = (id: string, signal: AbortSignal) =>
  api<DashboardDetails>(dashboardPath(id), { signal })
export const getCard = (dashboardId: string, cardId: string) => api<Card>(cardPath(dashboardId, cardId))
export const putVote = (dashboardId: string, cardId: string, cardVersion: number) =>
  api<Card>(cardPath(dashboardId, cardId) + '/vote', {
    method: 'PUT',
    body: JSON.stringify({ cardVersion }),
  })
export const removeVote = (dashboardId: string, cardId: string) =>
  api<void>(cardPath(dashboardId, cardId) + '/vote', { method: 'DELETE' })

export const saveCard = (dashboardId: string, trip: TripInput, cardId?: string) =>
  api<Card>(cardId ? cardPath(dashboardId, cardId) : dashboardPath(dashboardId) + '/cards', {
    method: cardId ? 'PUT' : 'POST',
    body: JSON.stringify(trip),
  })

export const publishCard = (dashboardId: string, cardId: string) =>
  api<Card>(cardPath(dashboardId, cardId) + '/publish', { method: 'POST' })

export const createInvite = (dashboardId: string) =>
  api<{ token: string }>(dashboardPath(dashboardId) + '/invite', { method: 'POST' })
