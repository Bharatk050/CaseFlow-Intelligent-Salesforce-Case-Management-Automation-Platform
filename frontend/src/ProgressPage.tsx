import { useEffect, useState } from 'react'

type Progress = { total_resolutions: number; period_resolutions: number; timezone: string; daily: { date: string; count: number }[] }

export function ProgressPage({ connected, api, onExpired }: {
  connected: boolean; api: <T>(path: string) => Promise<T>; onExpired: () => void
}) {
  const [days, setDays] = useState(30)
  const [retry, setRetry] = useState(0)
  const [data, setData] = useState<Progress | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let active = true
    setData(null); setError('')
    if (connected) {
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
      void api<Progress>(`/me/progress?days=${days}&timezone=${encodeURIComponent(zone)}`).then(result => {
        if (active) setData(result)
      }).catch(reason => {
        if (!active) return
        if (reason.status === 401) onExpired()
        setError(reason.message || 'Unable to load progress.')
      })
    }
    return () => { active = false }
  }, [connected, days, retry, api])
  if (!connected) return <section id="progress-content" className="progress-panel"><h2>Sign in to track your progress</h2><p>Connect Salesforce above to view your permanent progress. Excel beta activity stays in its temporary browser session.</p></section>
  const maximum = Math.max(1, ...(data?.daily.map(day => day.count) || []))
  return <section id="progress-content" className="progress-panel" aria-label="My resolution progress">
    <div className="progress-heading"><h2>My resolutions</h2><label>Period <select value={days} onChange={event => setDays(Number(event.target.value))}>{[7, 30, 90].map(value => <option key={value} value={value}>Last {value} days</option>)}</select></label></div>
    <p>Resolution actions recorded in this app on cases you can currently access. Resolving a reopened case counts again. Tracking starts with newly recorded resolutions.</p>
    {error ? <div role="alert"><p>{error}</p><button className="button button-secondary" onClick={() => setRetry(value => value + 1)}>Retry</button></div> : !data ? <p role="status">Loading progress...</p> : <>
      <div className="progress-totals"><div className="summary-card"><div className="summary-copy"><span>Total resolutions</span><strong>{data.total_resolutions}</strong></div></div><div className="summary-card"><div className="summary-copy"><span>Resolutions in selected period</span><strong>{data.period_resolutions}</strong></div></div></div>
      {!data.period_resolutions && <p>No resolutions in this period. Mark a case Resolved and save it to record your work.</p>}
      <h3>Daily resolutions</h3><p>Dates shown in {data.timezone}.</p>
      <svg className="progress-chart" viewBox="0 0 900 250" role="img" aria-labelledby="progress-chart-title progress-chart-description">
        <title id="progress-chart-title">Daily resolutions over the last {days} days</title>
        <desc id="progress-chart-description">{data.period_resolutions} resolutions. Exact daily counts are available in the table below.</desc>
        {[0, maximum].map(value => <g key={value}><text x="5" y={220 - value / maximum * 190}>{value}</text><line x1="35" x2="895" y1={215 - value / maximum * 190} y2={215 - value / maximum * 190} /></g>)}
        {data.daily.map((day, index) => <rect key={day.date} x={40 + index * 850 / days} y={215 - day.count / maximum * 190} width={Math.max(2, 850 / days - 3)} height={day.count / maximum * 190}><title>{day.date}: {day.count} resolutions</title></rect>)}
        <text x="40" y="245">{data.daily[0].date}</text><text x="890" y="245" textAnchor="end">{data.daily[data.daily.length - 1].date}</text>
      </svg>
      <details><summary>View daily counts</summary><div className="progress-table"><table className="case-table"><caption>Daily resolutions ({data.timezone})</caption><thead><tr><th scope="col">Date</th><th scope="col">Resolutions</th></tr></thead><tbody>{data.daily.map(day => <tr key={day.date}><th scope="row">{day.date}</th><td>{day.count}</td></tr>)}</tbody></table></div></details>
    </>}
  </section>
}
