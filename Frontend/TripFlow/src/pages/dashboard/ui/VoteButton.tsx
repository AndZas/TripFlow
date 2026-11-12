import type { ButtonHTMLAttributes } from 'react'
import { Icon } from '../../../shared/ui/Icon'

export function VoteButton({ voted = false, children, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & {
  voted?: boolean
}) {
  return <button type="button" className={voted ? 'trip-heart is-voted' : 'trip-heart'} {...props}>
    <Icon name="heart" fill={voted ? 'currentColor' : 'none'} />
    {children}
  </button>
}
