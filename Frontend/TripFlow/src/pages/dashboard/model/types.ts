export type Card = {
  id: string
  authorId: string
  isPublished: boolean
  version: number
  voteCount: number
  myVoteVersion: number | null
  myVoteNeedsReview: boolean
  trip: TripInput
}

export type TripInput = {
    destinationId: string
    startDate: string
    endDate: string
    travelers: number
    budgetRub: number
    preferences: string | null
}

export type DashboardDetails = {
  ownerId: string
  name: string
  description: string | null
  memberCount: number
  cards: Card[]
}

export type Destination = { id: string; city: string }
