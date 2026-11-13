import { useEffect, useRef, useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api, errorMessage } from '../../shared/api/client'
import { Icon } from '../../shared/ui/Icon'
import './dashboards.css'

type DashboardSummary = { id: string; name: string; description: string | null }

function DashboardCard({ to, name, description }: {
  to: string
  name: string
  description: string | null
}) {
  return <li>
    <Link to={to} className="dashboard-card">
      <span className="icon-tile"><Icon name="grid" /></span>
      <span className="dashboard-card-copy">
        <strong className="dashboard-card-title">{name}</strong>
        {description && <span className="dashboard-card-description">{description}</span>}
      </span>
      <Icon name="arrowRight" className="card-arrow" />
    </Link>
  </li>
}

export function Dashboards() {
  const navigate = useNavigate()
  const createDialog = useRef<HTMLDialogElement>(null)
  const [dashboards, setDashboards] = useState<DashboardSummary[] | null>(null)
  const [loadError, setLoadError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const [createError, setCreateError] = useState('')
  const [pending, setPending] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    api<DashboardSummary[]>('/dashboards', { signal: controller.signal })
      .then(setDashboards)
      .catch(error => { if (!controller.signal.aborted) setLoadError(errorMessage(error)) })
    return () => controller.abort()
  }, [attempt])

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const name = String(fields.get('name')).trim()
    if (!name) {
      setCreateError('Введите название дашборда.')
      return
    }
    setCreateError('')
    setPending(true)
    try {
      const dashboard = await api<DashboardSummary>('/dashboards', {
        method: 'POST',
        body: JSON.stringify({ name, description: String(fields.get('description')).trim() || null }),
      })
      createDialog.current?.close()
      navigate('/dashboards/' + dashboard.id)
    } catch (error) {
      setCreateError(errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  const openCreate = () => createDialog.current?.showModal()

  return <>
    <section className="atlas-hero dashboards-hero">
      <div className="hero-content">
        <p className="eyebrow"><Icon name="compass" /> Пространство для путешествий</p>
        <h1>Мои дашборды</h1>
        <p className="hero-description">Соберите варианты поездки в одном месте и выберите лучший вместе с друзьями.</p>
        <button className="hero-action" type="button" onClick={openCreate}>
          <Icon name="plus" /> Новый дашборд
        </button>
      </div>
    </section>
    <div className="dashboard-collections">
      <section aria-labelledby="personal-boards">
        <div className="collection-heading">
          <h2 id="personal-boards">Личные дашборды</h2>
          {dashboards && <span className="count-badge" aria-label={`Всего: ${dashboards.length}`}>{dashboards.length}</span>}
        </div>
        {loadError ? <div className="panel collection-status"><p role="alert">{loadError}</p><button className="secondary" onClick={() => {
          setLoadError('')
          setAttempt(value => value + 1)
        }}>Повторить</button></div> : dashboards === null ? <div className="panel collection-status" role="status">Загружаем дашборды…</div>
          : dashboards.length === 0 ? <div className="dashboard-empty">
            <span className="icon-tile"><Icon name="grid" /></span>
            <h3>Здесь появятся ваши поездки</h3>
            <p>Создайте дашборд и пригласите тех, с кем хотите поехать.</p>
            <button type="button" className="secondary" onClick={openCreate}><Icon name="plus" /> Создать дашборд</button>
          </div> : <ul className="dashboard-card-list">
            {dashboards.map(({ id, name, description }) =>
              <DashboardCard key={id} to={'/dashboards/' + id} name={name} description={description} />)}
          </ul>}
      </section>
      <section aria-labelledby="demo-board">
        <div className="collection-heading"><h2 id="demo-board">Попробовать демо</h2></div>
        <Link to="/dashboards/demo" className="demo-card">
          <span className="demo-card-art"><span className="demo-tag"><Icon name="pin" /> Москва</span></span>
          <span className="demo-card-copy">
            <strong className="dashboard-card-title">Поездка в Москву</strong>
            <span className="dashboard-card-description">Сравните два плана и попробуйте проголосовать.</span>
            <span className="demo-card-action">Открыть демо <Icon name="arrowRight" /></span>
          </span>
        </Link>
      </section>
    </div>
    <dialog ref={createDialog} aria-labelledby="create-dashboard-title"
      onClose={() => setCreateError('')}
      onCancel={event => { if (pending) event.preventDefault() }}>
      <span className="icon-tile dialog-icon"><Icon name="grid" /></span>
      <h2 id="create-dashboard-title">Новый дашборд</h2>
      <form onSubmit={create}>
        <label>Название<input name="name" required maxLength={100} placeholder="Например, Июньские выходные" /></label>
        <label>Описание (необязательно)<textarea name="description" maxLength={1000} rows={3} /></label>
        {createError && <p role="alert">{createError}</p>}
        <div className="dialog-actions">
          <button type="button" className="secondary" disabled={pending}
            onClick={() => createDialog.current?.close()}>Отмена</button>
          <button disabled={pending}>{pending ? 'Создаём…' : 'Создать дашборд'}</button>
        </div>
      </form>
    </dialog>
  </>
}
