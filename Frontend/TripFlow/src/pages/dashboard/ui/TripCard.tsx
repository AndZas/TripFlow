import type { ReactNode } from 'react'
import { Icon } from '../../../shared/ui/Icon'
import type { Card, Destination } from '../model/types'

export const rubles = new Intl.NumberFormat('ru-RU', {
  style: 'currency', currency: 'RUB', maximumFractionDigits: 0,
})
const dates = new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeZone: 'UTC' })
const nightPlural = new Intl.PluralRules('ru-RU')
const nightUnits: Partial<Record<Intl.LDMLPluralRule, string>> = { one: 'ночь', few: 'ночи' }

export function TripCard({ card, destinations, title, label, alternateArt = false, plan, children }: {
  card: Card
  destinations: Destination[]
  title?: string
  label?: string
  alternateArt?: boolean
  plan?: ReactNode
  children?: ReactNode
}) {
  const { trip } = card
  const isMoscow = trip.destinationId === 'ru-moscow'
  const city = destinations.find(destination => destination.id === trip.destinationId)?.city ?? (isMoscow ? 'Москва' : undefined)
  const heading = <h3>{title ?? city ?? trip.destinationId}</h3>
  const start = new Date(trip.startDate)
  const end = new Date(trip.endDate)
  const nights = (end.getTime() - start.getTime()) / 86_400_000
  const nightUnit = nightUnits[nightPlural.select(nights)] ?? 'ночей'

  return <li className="panel trip-card">
    <div className={`trip-card-art${isMoscow ? ' trip-card-art-moscow' : ''}${alternateArt ? ' trip-card-art-alternate' : ''}`}
      aria-hidden="true" />
    <div className={label ? 'trip-card-heading has-label' : 'trip-card-heading'}>
      {label ? <p className="trip-label">{label}</p> : heading}
      <span className="trip-card-status" aria-live="polite">
        {card.isPublished && <Icon name="heart" />}
        {card.isPublished ? 'Голоса: ' + card.voteCount : 'Черновик'}
      </span>
      {label && heading}
    </div>
    <p className="trip-card-date"><Icon name="calendar" />
      <span>{dates.formatRange(start, end)} · {nights === 0 ? 'Без ночёвки' : `${nights} ${nightUnit}`}</span>
    </p>
    <dl className="trip-facts">
      <div><dt>Целевой бюджет</dt><dd>{rubles.format(trip.budgetRub)}</dd></div>
      <div><dt>Путешественники</dt><dd>{trip.travelers}</dd></div>
    </dl>
    {trip.preferences && <p className="trip-preferences">{trip.preferences}</p>}
    {plan && <details className="trip-plan">
      <summary><span>План и расходы <small>Демо</small></span>
        <Icon name="chevron" />
      </summary>
      <div className="trip-example">{plan}</div>
    </details>}
    {children && <div className="trip-card-footer">{children}</div>}
  </li>
}
