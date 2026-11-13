import { createRoot } from 'react-dom/client'
import { useEffect, useState, useSyncExternalStore } from 'react'
import { BrowserRouter, Link, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom'
import './styles.css'
import { SignIn } from '../pages/sign-in/SignIn'
import { SignUp } from '../pages/sign-up/SignUp'
import { Dashboards } from '../pages/dashboards/Dashboards'
import { Dashboard, DemoDashboard } from '../pages/dashboard'
import { JoinDashboard } from '../pages/join-dashboard'
import { getAccount, type Account } from '../shared/api/account'
import { api, getToken, setToken, subscribeToSession } from '../shared/api/client'
import { Brand, Icon } from '../shared/ui/Icon'

function PrivateLayout() {
  const token = useSyncExternalStore(subscribeToSession, getToken)
  const location = useLocation()
  const [account, setAccount] = useState<Account | null>(null)
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    const { signal } = controller
    getAccount(signal).then(setAccount).catch(() => {})
    api<{ status: string }>('/health', { signal })
      .then(result => setUnavailable(result.status !== 'ok'))
      .catch(() => { if (!signal.aborted) setUnavailable(true) })
    return () => controller.abort()
  }, [token])
  if (!token) return <Navigate to="/sign-in" state={{ from: location.pathname }} replace />

  async function logout() {
    try {
      await api<void>('/auth/logout', { method: 'POST' })
    } catch {
      // A local sign-out is still possible when the server is unavailable.
    } finally {
      if (getToken() === token) setToken(null)
    }
  }

  return <>
    <header className="site-header"><nav aria-label="Основная навигация">
      <Link to="/dashboards" className="brand-link"><Brand /></Link>
      <div className="account-actions">
        {account && <span className="account-identity">
          <span className="account-avatar" aria-hidden="true">{account.email.slice(0, 1).toUpperCase()}</span>
          <span className="account-email">{account.email}</span>
        </span>}
        <button className="secondary logout" onClick={logout}><Icon name="logout" /> Выйти</button>
      </div>
    </nav></header>
    <main className="site-main">
      {unavailable && <p className="notice server-notice" role="status"><Icon name="info" />
        Сервер TripFlow недоступен. Обновите страницу, чтобы проверить подключение.
      </p>}
      <Outlet context={account} />
    </main>
    <footer className="site-footer"><span>TripFlow</span><span>Планируйте поездки вместе</span></footer>
  </>
}

createRoot(document.getElementById('root')!).render(
  <BrowserRouter>
    <Routes>
      <Route path="/sign-in" element={<SignIn />} />
      <Route path="/sign-up" element={<SignUp />} />
      <Route element={<PrivateLayout />}>
        <Route path="/" element={<Navigate to="/dashboards" replace />} />
        <Route path="/dashboards" element={<Dashboards />} />
        <Route path="/dashboards/demo" element={<DemoDashboard />} />
        <Route path="/dashboards/:id" element={<Dashboard />} />
        <Route path="/join/:token" element={<JoinDashboard />} />
        <Route path="*" element={<><h1>Страница не найдена</h1><Link to="/dashboards">Мои дашборды</Link></>} />
      </Route>
    </Routes>
  </BrowserRouter>,
)
