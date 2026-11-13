import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api, ApiError, errorMessage } from '../../shared/api/client'
import { Icon } from '../../shared/ui/Icon'

export function JoinDashboard() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function join() {
    setPending(true)
    setError('')
    try {
      const dashboard = await api<{ id: string }>('/dashboards/join', {
        method: 'POST', body: JSON.stringify({ token }),
      })
      navigate('/dashboards/' + dashboard.id, { replace: true })
    } catch (error) {
      setError(error instanceof ApiError && error.status === 404
        ? 'Приглашение недействительно. Попросите владельца прислать актуальную ссылку.'
        : errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  return <section className="panel join-panel">
    <span className="icon-tile"><Icon name="link" /></span>
    <h1>Приглашение в дашборд</h1>
    <p>После вступления дашборд появится в вашем списке.</p>
    {error && <p role="alert">{error}</p>}
    <div className="trip-actions">
      <button disabled={pending} onClick={join}>{pending ? 'Вступаем…' : 'Вступить'}</button>
      <Link className="button-link secondary" to="/dashboards">Мои дашборды</Link>
    </div>
  </section>
}
