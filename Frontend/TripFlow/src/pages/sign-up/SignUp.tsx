import { useState, useSyncExternalStore, type FormEvent } from 'react'
import { Link, Navigate, useLocation } from 'react-router-dom'
import { returnPath } from '../../shared/api/account'
import { api, errorMessage, getToken, setToken, subscribeToSession } from '../../shared/api/client'
import { AuthLayout } from '../../shared/ui/AuthLayout'

export function SignUp() {
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
      const session = await api<{ accessToken: string }>('/auth/register', {
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

  return <AuthLayout title="Регистрация" description="Создайте аккаунт, чтобы планировать поездки с друзьями."
    alternate={<>Уже есть аккаунт? <Link to="/sign-in" state={state}>Войти</Link></>}>
    <form onSubmit={submit}>
      <label>Email<input type="email" name="email" autoComplete="username" maxLength={254} required /></label>
      <label>
        Пароль
        <input type="password" name="password" autoComplete="new-password" minLength={10}
          maxLength={128} aria-describedby="password-hint" required />
        <small id="password-hint">От 10 до 128 символов.</small>
      </label>
      {error && <p role="alert">{error}</p>}
      <button disabled={pending}>{pending ? 'Создаём аккаунт…' : 'Зарегистрироваться'}</button>
    </form>
  </AuthLayout>
}
