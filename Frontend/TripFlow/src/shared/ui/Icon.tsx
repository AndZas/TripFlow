import type { SVGProps } from 'react'

const paths = {
  arrowLeft: <path d="m12 5-7 7 7 7m-7-7h14" />,
  arrowRight: <path d="M5 12h14m-7-7 7 7-7 7" />,
  calendar: <><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M3 10h18M8 3v4m8-4v4" /></>,
  chevron: <path d="m6 9 6 6 6-6" />,
  compass: <><circle cx="12" cy="12" r="9" /><path d="m16 8-2.5 5.5L8 16l2.5-5.5L16 8Z" /></>,
  grid: <><rect x="3.5" y="3.5" width="6.5" height="6.5" rx="1.2" /><rect x="14" y="3.5" width="6.5" height="6.5" rx="1.2" /><rect x="3.5" y="14" width="6.5" height="6.5" rx="1.2" /><rect x="14" y="14" width="6.5" height="6.5" rx="1.2" /></>,
  heart: <path d="M12 21 3.7 12.7a5.2 5.2 0 0 1 7.4-7.4l.9.9.9-.9a5.2 5.2 0 1 1 7.4 7.4Z" />,
  info: <><circle cx="12" cy="12" r="9" /><path d="M12 11v5m0-8h.01" /></>,
  link: <path d="m10 13 4-4m-6 6-1 1a3.5 3.5 0 0 1-5-5l4-4a3.5 3.5 0 0 1 5 0m2 10a3.5 3.5 0 0 0 5 0l4-4a3.5 3.5 0 0 0-5-5l-1 1" transform="translate(1 1) scale(.92)" />,
  logout: <><path d="M11 20H6a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5m-1 8h10m-4-4 4 4-4 4" /></>,
  pin: <><path d="M19 10c0 5-7 10-7 10S5 15 5 10a7 7 0 1 1 14 0Z" /><circle cx="12" cy="10" r="2.25" /></>,
  plus: <path d="M12 5v14M5 12h14" />,
  users: <><circle cx="9" cy="8" r="3" /><path d="M3 20v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2M16 5a3 3 0 0 1 0 6m5 9v-2a4 4 0 0 0-3-3.9" /></>,
}

export function Icon({ name, ...props }: SVGProps<SVGSVGElement> & { name: keyof typeof paths }) {
  return <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor"
    strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>
    {paths[name]}
  </svg>
}

export function Brand() {
  return <span className="brand"><span className="brand-mark"><Icon name="compass" /></span>TripFlow</span>
}
