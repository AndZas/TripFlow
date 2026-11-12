import type { ReactNode } from 'react'
import { Brand } from './Icon'

export function AuthLayout({ title, description, children, alternate }: {
  title: string
  description: string
  children: ReactNode
  alternate: ReactNode
}) {
  return <main className="auth">
    <div className="auth-layout">
      <aside className="auth-atlas atlas-hero">
        <Brand />
        <div className="auth-message">
          <p className="eyebrow">Совместные путешествия</p>
          <p className="auth-display">Следующая поездка начинается здесь.</p>
          <p>Собирайте варианты и выбирайте маршрут вместе.</p>
        </div>
      </aside>
      <section className="auth-content" aria-labelledby="auth-title">
        <h1 id="auth-title">{title}</h1>
        <p className="auth-description">{description}</p>
        {children}
        <p className="auth-alternate">{alternate}</p>
      </section>
    </div>
  </main>
}
