import { useState } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { Icon } from '../../../shared/ui/Icon'
import { createInvite } from '../api/dashboard'

export function InviteControls({ dashboardId }: { dashboardId: string }) {
  const [link, setLink] = useState('')
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')

  async function generate() {
    setPending(true)
    setError('')
    setMessage('')
    try {
      const { token } = await createInvite(dashboardId)
      setLink(new URL('/join/' + encodeURIComponent(token), location.origin).href)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(link)
      setMessage('Ссылка скопирована.')
    } catch {
      setMessage('Выделите ссылку и скопируйте вручную.')
    }
  }

  return <section className="panel trip-invite">
    <span className="icon-tile"><Icon name="link" /></span>
    <div className="invite-copy">
      <h3>Пригласите попутчиков</h3>
      <p>При создании новой ссылки предыдущая перестаёт действовать.</p>
    </div>
    <button className="secondary" type="button" disabled={pending} onClick={generate}>
      {pending ? 'Создаём ссылку…' : link ? 'Обновить ссылку' : 'Создать ссылку-приглашение'}
    </button>
    <div className="invite-feedback" hidden={!link && !message && !error}>
      {link && <label>Ссылка для приглашения<input value={link} readOnly onFocus={event => event.target.select()} /></label>}
      {link && <button type="button" onClick={copy}>Скопировать</button>}
      {message && <p role="status">{message}</p>}
      {error && <p role="alert">{error}</p>}
    </div>
  </section>
}
