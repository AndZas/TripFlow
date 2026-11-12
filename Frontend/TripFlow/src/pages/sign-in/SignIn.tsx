import { useState, useSyncExternalStore, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { returnPath } from '../../shared/api/account'
import { api, errorMessage, getToken, setToken, subscribeToSession } from '../../shared/api/client'
import { AuthLayout } from '../../shared/ui/AuthLayout'

export function SignIn() {
  const token = useSyncExternalStore(subscribeToSession, getToken)
  const { state } = useLocation()
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const destination = returnPath(state)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    setError('')
    setPending(true)
    try {
      const session = await api<{ accessToken: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: String(fields.get('email')).trim(), password: fields.get('password') }),
      })
      setToken(session.accessToken)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  if (token) return <Navigate to={destination} replace />

  return <AuthLayout title="Вход" description="Войдите, чтобы вернуться к своим поездкам."
    alternate={<>Нет аккаунта? <Link to="/sign-up" state={state}>Зарегистрироваться</Link></>}>
    <form onSubmit={submit}>
      <label>Email<input type="email" name="email" autoComplete="username" required /></label>
      <label>Пароль<input type="password" name="password" autoComplete="current-password" required /></label>
      {error && <p role="alert">{error}</p>}
      <button disabled={pending}>{pending ? 'Входим…' : 'Войти'}</button>
    </form>
  </AuthLayout>
}
