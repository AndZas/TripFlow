import type { Card } from './types'

const sample = { authorId: 'demo', isPublished: true, version: 1, myVoteVersion: null, myVoteNeedsReview: false }

export const demoCards: Card[] = [
  {
    ...sample,
    id: 'readme-example',
    voteCount: 2,
    trip: {
      destinationId: 'ru-moscow',
      startDate: '2027-06-10',
      endDate: '2027-06-15',
      travelers: 2,
      budgetRub: 75000,
      preferences: 'Музеи и парки',
    },
  },
  {
    ...sample,
    id: 'demo-weekend',
    voteCount: 1,
    trip: {
      destinationId: 'ru-moscow',
      startDate: '2027-06-18',
      endDate: '2027-06-20',
      travelers: 2,
      budgetRub: 35000,
      preferences: 'Прогулки в центре и выставки',
    },
  },
]

export const demoDetails: Record<string, {
  title: string
  hotel: string
  places: string[]
  expenses: { label: string; amount: number }[]
}> = {
  'readme-example': {
    title: 'Пять ночей в Москве',
    hotel: 'Условный отель рядом с метро',
    places: ['Третьяковская галерея', 'Парк Горького'],
    expenses: [
      { label: 'Проживание', amount: 34000 },
      { label: 'Питание', amount: 18000 },
      { label: 'Достопримечательности', amount: 6000 },
      { label: 'Транспорт', amount: 4000 },
      { label: 'Резерв', amount: 7000 },
    ],
  },
  'demo-weekend': {
    title: 'Выходные в Москве',
    hotel: 'Условный мини-отель в центре',
    places: ['Музей Москвы', 'Зарядье'],
    expenses: [
      { label: 'Проживание', amount: 16000 },
      { label: 'Питание', amount: 8000 },
      { label: 'Достопримечательности', amount: 2500 },
      { label: 'Транспорт', amount: 1500 },
      { label: 'Резерв', amount: 3500 },
    ],
  },
}
