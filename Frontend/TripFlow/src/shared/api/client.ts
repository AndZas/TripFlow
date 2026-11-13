let accessToken = sessionStorage.getItem('tripflow.accessToken')
const sessionEvents = new EventTarget()

export function getToken() {
  return accessToken
}

export function setToken(token: string | null) {
  accessToken = token
  if (token) sessionStorage.setItem('tripflow.accessToken', token)
  else sessionStorage.removeItem('tripflow.accessToken')
  sessionEvents.dispatchEvent(new Event('change'))
}

export function subscribeToSession(callback: () => void) {
  sessionEvents.addEventListener('change', callback)
  return () => sessionEvents.removeEventListener('change', callback)
}

type Problem = { detail?: string; errors?: Record<string, string[]> }

export class ApiError extends Error {
  constructor(readonly status: number, message: string) {
    super(message)
  }
}

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const headers = new Headers(options.headers)
  if (options.body) headers.set('Content-Type', 'application/json')
  if (token) headers.set('Authorization', 'Bearer ' + token)
  const response = await fetch('/api' + path, { ...options, headers })
  if (!response.ok) {
    if (response.status === 401 && token && token === getToken()) setToken(null)
    const problem: Problem | null = await response.json().catch(() => null)
    const fields = problem?.errors ? Object.values(problem.errors).flat().join(' ') : ''
    const fallback = {
      400: 'Проверьте введённые данные.',
      401: 'Проверьте email и пароль или войдите заново.',
      403: 'Недостаточно прав.',
      404: 'Страница не найдена или доступ к ней закрыт.',
      409: path === '/auth/register' ? 'Этот email уже зарегистрирован.' : 'Данные изменились. Повторите запрос.',
    }[response.status] ?? 'Сервер вернул ошибку (' + response.status + ').'
    throw new ApiError(response.status, fields || problem?.detail || fallback)
  }
  if (response.status === 204) return undefined as T
  return response.json()
}

export function errorMessage(error: unknown) {
  if (error instanceof TypeError) return 'Не удалось связаться с сервером. Попробуйте ещё раз.'
  return error instanceof Error ? error.message : 'Не удалось выполнить запрос.'
}
