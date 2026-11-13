import { useEffect, useState } from 'react'
import { Link, useOutletContext, useParams } from 'react-router-dom'
import { ApiError, errorMessage } from '../../../shared/api/client'
import type { Account } from '../../../shared/api/account'
import { Icon } from '../../../shared/ui/Icon'
import { demoCards, demoDetails } from '../model/demo'
import type { Card, DashboardDetails, Destination } from '../model/types'
import { getDashboard, getDestinations, getCard, putVote, removeVote, publishCard } from '../api/dashboard'
import { TripCard, rubles } from './TripCard'
import { VoteButton } from './VoteButton'
import { CardEditor } from './CardEditor'
import { InviteControls } from './InviteControls'
import './dashboard.css'

export function Dashboard() {
  const { id } = useParams()
  return id ? <DashboardScreen key={id} id={id} /> : null
}

function useDestinations() {
  const [destinations, setDestinations] = useState<Destination[]>([])
  useEffect(() => {
    const controller = new AbortController()
    getDestinations(controller.signal)
      .then(setDestinations)
      .catch(() => {})
    return () => controller.abort()
  }, [])
  return destinations
}

function DashboardScreen({ id }: { id: string }) {
  const account = useOutletContext<Account | null>()
  const [dashboard, setDashboard] = useState<DashboardDetails | null>(null)
  const [editor, setEditor] = useState<{ card?: Card } | null>(null)
  const [error, setError] = useState('')
  const [attempt, setAttempt] = useState(0)
  const destinations = useDestinations()

  useEffect(() => {
    const controller = new AbortController()
    getDashboard(id, controller.signal)
      .then(setDashboard)
      .catch(error => { if (!controller.signal.aborted) setError(errorMessage(error)) })
    return () => controller.abort()
  }, [id, attempt])

  function updateCard(updated: Card) {
    setDashboard(current => current && {
      ...current,
      cards: current.cards.some(card => card.id === updated.id)
        ? current.cards.map(card => card.id === updated.id ? updated : card)
        : [...current.cards, updated],
    })
  }

  return <div className="trip-board">
    <BackToBoards />
    {error ? <div className="panel collection-status"><p role="alert">{error}</p><button className="secondary" onClick={() => {
      setError('')
      setAttempt(value => value + 1)
    }}>Повторить</button></div> : !dashboard ? <p className="panel" role="status">Загружаем дашборд…</p> : <>
      <BoardHeading dashboard={dashboard} />
      {account?.id === dashboard.ownerId && <InviteControls dashboardId={id} />}
      <div className="trip-section-heading">
        <h2>Варианты поездки <span className="count-badge">{dashboard.cards.length}</span></h2>
        <button type="button" onClick={() => setEditor({})}><Icon name="plus" /> Добавить вариант</button>
      </div>
      {dashboard.cards.length === 0
        ? <div className="panel trip-empty">
          <span className="icon-tile"><Icon name="pin" /></span>
          <h3>Вариантов пока нет</h3>
          <p>Добавьте направление, даты и бюджет первой поездки.</p>
          <Link to="/dashboards/demo" className="button-link secondary">
            Посмотреть пример <Icon name="arrowRight" />
          </Link>
        </div>
        : <ul className="trip-grid">{dashboard.cards.map(card =>
          <TripCard key={card.id} card={card} destinations={destinations}>
            {account?.id === card.authorId && <CardActions card={card} dashboardId={id}
              onEdit={card => setEditor({ card })} onUpdate={updateCard} />}
            {card.isPublished && <VoteControls card={card} dashboardId={id} onUpdate={updateCard} />}
          </TripCard>)}</ul>}
      {editor && <CardEditor dashboardId={id} card={editor.card} destinations={destinations}
        onClose={() => setEditor(null)} onSave={card => { updateCard(card); setEditor(null) }} />}
    </>}
  </div>
}

export function DemoDashboard() {
  const destinations = useDestinations()
  const [votes, setVotes] = useState<Record<string, boolean>>({})
  return <div className="trip-board">
    <BackToBoards />
    <BoardHeading dashboard={{ name: 'Поездка в Москву', memberCount: 3,
      description: 'Сравните два плана поездки и проголосуйте за тот, который вам ближе.' }} demo />
    <p className="notice"><Icon name="info" /> Планы и расходы в демо условные. Голоса действуют только на этой странице.</p>
    <div className="trip-section-heading"><h2>Варианты поездки <span className="count-badge">{demoCards.length}</span></h2></div>
    <ul className="trip-grid">{demoCards.map((card, index) => {
      const details = demoDetails[card.id]
      const voted = Boolean(votes[card.id])
      return <TripCard key={card.id} card={{ ...card, voteCount: card.voteCount + Number(voted) }}
        destinations={destinations} title={details.title} label={`Вариант ${String(index + 1).padStart(2, '0')}`}
        alternateArt={card.id === 'demo-weekend'} plan={<>
          <p><strong>Проживание:</strong> {details.hotel}</p>
          <p><strong>Места:</strong> {details.places.join(' · ')}</p>
          <dl className="trip-costs">{details.expenses.map(({ label, amount }) =>
            <div key={label}><dt>{label}</dt><dd>{rubles.format(amount)}</dd></div>)}
            <div className="trip-total"><dt>Оценка на группу</dt>
              <dd>{rubles.format(details.expenses.reduce((total, row) => total + row.amount, 0))}</dd></div>
          </dl>
        </>}>
        <VoteButton voted={voted} onClick={() => setVotes(current => ({
          ...current, [card.id]: !current[card.id],
        }))}>{voted ? 'Снять голос' : 'Проголосовать'}</VoteButton>
      </TripCard>
    })}</ul>
  </div>
}

function BackToBoards() {
  return <Link to="/dashboards" className="trip-back">
    <Icon name="arrowLeft" /> Мои дашборды
  </Link>
}

function BoardHeading({ dashboard, demo = false }: {
  dashboard: { name: string; description?: string | null; memberCount: number }
  demo?: boolean
}) {
  return <section className="atlas-hero trip-heading">
    <div className="hero-content">
      <p className="eyebrow"><Icon name={demo ? 'compass' : 'grid'} /> {demo ? 'Демо-дашборд' : 'Дашборд поездки'}</p>
      <h1>{dashboard.name}</h1>
      {dashboard.description && <p className="hero-description">{dashboard.description}</p>}
      <p className="trip-members"><Icon name="users" />
        <span>{demo ? 'Участники демо:' : 'Участники:'} <strong>{dashboard.memberCount}</strong></span>
      </p>
    </div>
  </section>
}

function CardActions({ card, dashboardId, onEdit, onUpdate }: {
  card: Card
  dashboardId: string
  onEdit: (card: Card) => void
  onUpdate: (card: Card) => void
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')

  async function act(action: 'edit' | 'publish') {
    setPending(true)
    setError('')
    try {
      if (action === 'edit') onEdit(await getCard(dashboardId, card.id))
      else onUpdate(await publishCard(dashboardId, card.id))
    } catch (error) {
      setError(errorMessage(error))
    } finally {
      setPending(false)
    }
  }

  return <div>
    <div className="trip-actions">
      <button type="button" className="secondary" disabled={pending} onClick={() => act('edit')}>Редактировать</button>
      {!card.isPublished && <button type="button" disabled={pending} onClick={() => act('publish')}>Опубликовать</button>}
    </div>
    {error && <p role="alert">{error}</p>}
  </div>
}

function VoteControls({ card, dashboardId, onUpdate }: {
  card: Card
  dashboardId: string
  onUpdate: (card: Card) => void
}) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const hasVote = card.myVoteVersion != null

  async function vote(remove = false) {
    setPending(true)
    setError('')
    try {
      if (remove) {
        await removeVote(dashboardId, card.id)
        onUpdate(await getCard(dashboardId, card.id))
      } else {
        onUpdate(await putVote(dashboardId, card.id, card.version))
      }
    } catch (error) {
      if (error instanceof ApiError && error.status === 409) {
        try {
          onUpdate(await getCard(dashboardId, card.id))
          setError('Карточка изменилась. Проверьте параметры перед голосованием.')
        } catch (refreshError) {
          setError(errorMessage(refreshError))
        }
      } else {
        setError(errorMessage(error))
      }
    } finally {
      setPending(false)
    }
  }

  return <div className="trip-vote">
    {card.myVoteNeedsReview && <p className="notice"><Icon name="info" /> Карточка изменилась после вашего голоса.</p>}
    <div className="trip-actions">
      {(!hasVote || card.myVoteNeedsReview) && <VoteButton disabled={pending} onClick={() => vote()}>
        {hasVote ? 'Подтвердить голос' : 'Проголосовать'}
      </VoteButton>}
      {hasVote && <VoteButton voted disabled={pending} onClick={() => vote(true)}>Снять голос</VoteButton>}
    </div>
    {error && <p role="alert">{error}</p>}
  </div>
}
