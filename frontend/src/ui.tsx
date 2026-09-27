import type { ReactNode } from 'react'

export type IconName = 'layers' | 'inbox' | 'cloud' | 'sync' | 'disconnect' | 'upload' | 'search' | 'chevron' | 'sparkles' | 'shield' | 'clock' | 'user' | 'check' | 'file' | 'book' | 'arrow' | 'activity' | 'alert' | 'close' | 'filter' | 'save'

export function Icon({ name, className = '' }: { name: IconName; className?: string }) {
  const paths: Record<IconName, ReactNode> = {
    layers: <><path d="m12 3 9 5-9 5-9-5 9-5Z" /><path d="m3 12 9 5 9-5M3 16l9 5 9-5" /></>,
    inbox: <><path d="M4 4h16l2 11v5H2v-5L4 4Z" /><path d="M2 15h6l2 3h4l2-3h6M8 8h8M8 11h8" /></>,
    cloud: <path d="M6 18a4 4 0 0 1-1-7.9A7 7 0 0 1 18.5 9 4.5 4.5 0 0 1 0 9H6Z" />,
    sync: <><path d="M20 7a8 8 0 0 0-14-2L3 8m0-5v5h5M4 17a8 8 0 0 0 14 2l3-3m0 5v-5h-5" /></>,
    disconnect: <><path d="m8 3 3 3m5-3 3 3M9 7l8 8-3 3a5 5 0 0 1-7-7l2-2m-4 9-3 3M3 3l18 18" /></>,
    upload: <><path d="M12 16V3m-5 5 5-5 5 5M4 15v5h16v-5" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    chevron: <path d="m9 5 7 7-7 7" />,
    sparkles: <><path d="m12 3 2.4 6.6L21 12l-6.6 2.4L12 21l-2.4-6.6L3 12l6.6-2.4L12 3Z" /><path d="M20 2v4m-2-2h4" /></>,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6l8-3Z" /><path d="m8 12 3 3 5-6" /></>,
    clock: <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
    user: <><circle cx="12" cy="8" r="4" /><path d="M4 21v-2a8 8 0 0 1 16 0v2" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    file: <><path d="M14 3H5v18h14V8l-5-5Z" /><path d="M14 3v5h5M8 12h8M8 16h6" /></>,
    book: <><path d="M12 5c-3-2-6-2-10-1v15c4-1 7-1 10 1 3-2 6-2 10-1V4c-4-1-7-1-10 1Zm0 0v15" /></>,
    arrow: <><path d="M4 12h16m-6-6 6 6-6 6" /></>,
    activity: <path d="M2 12h5l3-8 4 16 3-8h5" />,
    alert: <><path d="m12 3 10 18H2L12 3Z" /><path d="M12 9v5m0 3v.2" /></>,
    close: <path d="m6 6 12 12M6 18 18 6" />,
    filter: <><path d="M3 6h18M6 12h12M9 18h6" /></>,
    save: <><path d="M19 21H5a2 2 0 0 1-2-2V3h14l4 4v12a2 2 0 0 1-2 2Z" /><path d="M7 3v6h9V3M7 21v-8h10v8" /></>,
  }
  return <svg className={`icon ${className}`} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>
}

export const humanize = (value: string) => value.replace(/_/g, ' ').replace(/\b\w/g, letter => letter.toUpperCase())

export function Badge({ value, kind = 'status' }: { value: string; kind?: 'status' | 'priority' }) {
  const known = ['open', 'in_progress', 'resolved', 'closed', 'escalated', 'critical', 'high', 'medium', 'low'].includes(value) ? value : 'neutral'
  return <span className={`badge badge-${kind} badge-${known}`}><span className="badge-dot" />{humanize(value)}</span>
}

export function EmptyState({ icon = 'inbox', title, children, compact = false }: { icon?: IconName; title: string; children: ReactNode; compact?: boolean }) {
  return <div className={`empty-state ${compact ? 'empty-state-compact' : ''}`}><span className="empty-icon"><Icon name={icon} /></span><h3>{title}</h3><p>{children}</p></div>
}

export function GuidanceText({ text }: { text: string }) {
  return <div className="guidance-text">{text.split('\n').map((line, index) => {
    const step = line.match(/^\s*(\d+)[.)]\s+(.+)$/)
    if (step) return <div className="guidance-step" key={index}><span className="step-number">{step[1]}</span><p>{step[2]}</p></div>
    if (!line.trim()) return null
    return <p className="guidance-paragraph" key={index}>{line}</p>
  })}</div>
}
