import { useEffect, useRef, useState, type FormEvent } from 'react'
import { errorMessage } from '../../../shared/api/client'
import { Icon } from '../../../shared/ui/Icon'
import { saveCard } from '../api/dashboard'
import type { Card, Destination, TripInput } from '../model/types'

export function CardEditor({ dashboardId, card, destinations, onClose, onSave }: {
  dashboardId: string
  card?: Card
  destinations: Destination[]
  onClose: () => void
  onSave: (card: Card) => void
}) {
  const dialog = useRef<HTMLDialogElement>(null)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [startDate, setStartDate] = useState(card?.trip.startDate ?? '')

  useEffect(() => { dialog.current?.showModal() }, [])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const fields = new FormData(event.currentTarget)
    const input: TripInput = {
      destinationId: String(fields.get('destinationId')),
      startDate,
      endDate: String(fields.get('endDate')),
      travelers: Number(fields.get('travelers')),
      budgetRub: Number(fields.get('budgetRub')),
      preferences: String(fields.get('preferences')).trim() || null,
    }
    setPending(true)
    setError('')
    try {
      const saved = await saveCard(dashboardId, input, card?.id)
      dialog.current?.close()
      onSave(saved)
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  return <dialog ref={dialog} className="trip-editor" aria-labelledby="trip-editor-title"
    onClose={onClose} onCancel={event => { if (pending) event.preventDefault() }}>
    <span className="icon-tile dialog-icon"><Icon name="pin" /></span>
    <h2 id="trip-editor-title">{card ? 'Редактировать вариант' : 'Новый вариант поездки'}</h2>
    <form onSubmit={submit}>
      <label>Направление
        <select name="destinationId" defaultValue={card?.trip.destinationId ?? ''} required>
          <option value="" disabled>Выберите город</option>
          {destinations.map(({ id, city }) => <option key={id} value={id}>{city}</option>)}
        </select>
      </label>
      {destinations.length === 0 && <p>Справочник направлений пока недоступен.</p>}
      <div className="trip-editor-fields">
        <label>Начало<input type="date" name="startDate" value={startDate} required
          onChange={event => setStartDate(event.target.value)} /></label>
        <label>Окончание<input type="date" name="endDate" min={startDate} required defaultValue={card?.trip.endDate} /></label>
        <label>Путешественники<input type="number" name="travelers" min={1} max={2147483647} required defaultValue={card?.trip.travelers ?? 1} /></label>
        <label>Бюджет группы, ₽<input type="number" name="budgetRub" min={1} max={Number.MAX_SAFE_INTEGER} required defaultValue={card?.trip.budgetRub} /></label>
      </div>
      <label>Предпочтения<textarea name="preferences" rows={3} maxLength={2000} defaultValue={card?.trip.preferences ?? ''} /></label>
      {error && <p role="alert">{error}</p>}
      <div className="dialog-actions">
        <button type="button" className="secondary" disabled={pending} onClick={() => dialog.current?.close()}>Отмена</button>
        <button disabled={pending || destinations.length === 0}>
          {pending ? 'Сохраняем…' : card ? 'Сохранить' : 'Создать черновик'}
        </button>
      </div>
    </form>
  </dialog>
}
