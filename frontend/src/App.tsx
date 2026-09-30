import { useEffect, useMemo, useRef, useState } from 'react'
import './styles.css'
import { ProgressPage } from './ProgressPage'
import { Badge, EmptyState, GuidanceBullets, GuidanceText, SavedGuidance, Icon, humanize, visibleGuidanceText } from './ui'
const API = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'https://localhost:8012' : window.location.origin)).replace(/\/$/, '')
type Connection = { configured: boolean; connected: boolean; display_name?: string | null; queues: { id: string; name: string }[]; selected_queue_id: string | null; last_synced_at: string | null; can_assign: boolean }
type Ticket = { response_type?: string; reply_available?: boolean; retrieval_mode?: string; description_missing?: boolean; guidance_stale?: boolean; case_summary?: string; missing_information?: string[]; reply_draft?: string; source?: string; imported_case_fields?: Record<string, string>; requires_human?: boolean; ai_mode?: string; created_at?: string; id: string; subject: string; customer: string; message: string; status: string; priority: string; owner?: string; resolution_note?: string; case_reason?: string; salesforce_case_id?: string; salesforce_case_number?: string; salesforce_status?: string; salesforce_priority?: string; salesforce_owner_id?: string; suggested_approach?: string; rationale?: string; ai_advisory_priority?: string; rag_articles?: { slug: string; title: string; sections?: { section_id: string; heading: string }[] }[]; activity?: { at: string; member_name: string; action: string }[] }
type Performance = { id: string; name: string; case_updates: number; suggestions_requested: number; cases_touched: number }
type StructuredGuidance = { answer_bullets?: { text: string; source_ids: string[] }[]; agent_steps?: { text: string; source_ids: string[] }[]; mandatory_constraints?: string[]; evidence_details?: { source_id: string; heading: string; text: string }[] }
const disconnected: Connection = { configured: false, connected: false, queues: [], selected_queue_id: null, last_synced_at: null, can_assign: false }
class ApiError extends Error {
  constructor(message: string, readonly status: number) { super(message) }
}
async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}${path}`, { ...options, credentials: 'include' })
  const body = response.status === 204 ? null : await response.json().catch(() => null)
  if (!response.ok) throw new ApiError(typeof body?.detail === 'string' ? body.detail : `Request failed (${response.status}).`, response.status)
  return body as T
}
const json = (body: unknown, method = 'POST'): RequestInit => ({ method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
type RosterResult = { state: 'found' | 'missing'; view: { id: string; label: string } | null; cases: Ticket[]; count: number; last_synced_at: string }
let rosterRequest: Promise<RosterResult> | undefined
const fetchRoster = () => rosterRequest ??= api<RosterResult>('/auth/salesforce/roster-support/sync', { method: 'POST' }).finally(() => { rosterRequest = undefined })
let betaStart: Promise<{ ready: boolean }> | undefined
const ensureBetaSession = () => betaStart ??= api<{ ready: boolean }>('/auth/local-beta', { method: 'POST' }).finally(() => { betaStart = undefined })
function App() {
  const [page, setPage] = useState(['#/progress', '#progress-content'].includes(window.location.hash) ? 'progress' : 'cases')
  const [connectionState, setConnectionState] = useState<'loading' | 'ready' | 'unconfigured' | 'failed'>('loading')
  useEffect(() => {
    const change = () => setPage(['#/progress', '#progress-content'].includes(window.location.hash) ? 'progress' : 'cases')
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  const [connection, setConnection] = useState<Connection>(disconnected)
  const [rosterState, setRosterState] = useState<'idle' | 'loading' | 'found' | 'missing' | 'error'>('idle')
  const [rosterCount, setRosterCount] = useState(0)
  const [rosterError, setRosterError] = useState('')
  const [tickets, setTickets] = useState<Ticket[]>([]), [selectedId, setSelectedId] = useState('')
  const [performance, setPerformance] = useState<Performance[]>([])
  const [query, setQuery] = useState(''), [status, setStatus] = useState(''), [priority, setPriority] = useState(''), [owner, setOwner] = useState(''), [reason, setReason] = useState('')
  const [notice, setNotice] = useState(''), [busy, setBusy] = useState(false)
  const [betaReady, setBetaReady] = useState(false)
  const [activeAction, setActiveAction] = useState('')
  const clearPrivateData = () => { setTickets([]); setPerformance([]); setSelectedId(''); setRosterState('idle'); setRosterCount(0); setRosterError('') }
  const refreshInFlight = useRef<Promise<void> | null>(null)
  const performRefresh = async () => {
    let local = false
    let connected = false
    try {
      local = (await ensureBetaSession()).ready
      setBetaReady(local)
    } catch { setBetaReady(false) }
    try {
      const next = await api<Connection>('/auth/salesforce/status')
      setConnectionState(next.configured ? 'ready' : 'unconfigured'); setConnection(next)
      connected = next.connected
    } catch (error) {
      setConnectionState('failed')
      setConnection(current => ({ ...disconnected, configured: current.configured || (error instanceof ApiError && error.status === 401) }))
      setNotice(`${error instanceof Error ? error.message : 'Salesforce is unavailable.'} Excel beta is independent of Salesforce.`)
    }
    if (!connected && !local) { clearPrivateData(); return }
    try {
      const scope = local ? '?local_only=true' : ''
      const [items, activity] = await Promise.all([api<Ticket[]>(`/tickets${scope}`), api<Performance[]>(`/team/performance${scope}`)])
      let rosterCases: Ticket[] = []
      if (connected) {
        setRosterState('loading'); setRosterError('')
        setTickets(items.filter(item => item.source !== 'salesforce'))
        try {
          const result = await fetchRoster()
          rosterCases = result.cases
          setRosterState(result.state); setRosterCount(result.count)
          setConnection(current => ({ ...current, last_synced_at: result.last_synced_at }))
        } catch (error) {
          if (error instanceof ApiError && error.status === 401) { setConnection(disconnected) }
          setRosterState('error'); setRosterCount(0)
          setRosterError(error instanceof Error ? error.message : 'Unable to retrieve the Salesforce list view.')
        }
      } else { setRosterState('idle'); setRosterCount(0) }
      const currentItems = [...rosterCases, ...items.filter(item => item.source !== 'salesforce')]
      setTickets(currentItems); setPerformance(activity)
      setSelectedId(current => currentItems.some(item => item.id === current) ? current : currentItems[0]?.id ?? '')
    } catch (error) { clearPrivateData(); throw error }
  }
  const refresh = () => refreshInFlight.current ??= performRefresh().finally(() => { refreshInFlight.current = null })
  useEffect(() => {
    const message = new URLSearchParams(window.location.search).get('salesforce_error')
    if (message) { setNotice(message); window.history.replaceState(null, '', window.location.pathname) }
    void refresh().catch(error => setNotice(String(error.message)))
  }, [])
  const run = async (action: () => Promise<void>) => {
    setBusy(true); setNotice('')
    try { await action() } catch (error) {
      if (error instanceof ApiError && error.status === 401) { clearPrivateData(); setConnection(current => ({ ...disconnected, configured: current.configured })) }
      setNotice(error instanceof Error ? error.message : 'Unable to complete request.')
    }
    finally { setBusy(false) }
  }
  const filtered = useMemo(() => tickets.filter(ticket =>
    (!query || `${ticket.subject} ${ticket.customer} ${ticket.message} ${ticket.salesforce_case_number ?? ''}`.toLowerCase().includes(query.toLowerCase())) &&
    (!status || ticket.status === status) && (!priority || ticket.priority === priority) &&
    (!owner || (ticket.owner || ticket.salesforce_owner_id) === owner) && (!reason || ticket.case_reason === reason)
  ), [tickets, query, status, priority, owner, reason])
  const selected = filtered.find(ticket => ticket.id === selectedId) ?? filtered[0]
  const values = (field: 'status' | 'priority' | 'case_reason') => [...new Set(tickets.map(ticket => ticket[field]).filter((value): value is string => Boolean(value)))]
  const update = async (path: string, options: RequestInit) => {
    const item = await api<Ticket>(path, options)
    setTickets(current => current.map(ticket => ticket.id === item.id ? item : ticket))
    try { setPerformance(await api<Performance[]>(`/team/performance${connection.connected ? '' : '?local_only=true'}`)) }
    catch { setNotice('Case saved. Activity totals could not be refreshed.') }
  }
  const connectSalesforce = () => void run(async () => {
    setConnectionState('loading')
    try {
      const next = await api<Connection>('/auth/salesforce/status')
      setConnection(next)
      setConnectionState(next.configured ? 'ready' : 'unconfigured')
      if (!next.configured) { setNotice('Salesforce OAuth is not configured on this server. Ask your administrator to check the server settings.'); return }
    } catch (error) {
      // An expired cookie must not prevent a fresh OAuth login.
      if (!(error instanceof ApiError && error.status === 401)) {
        setConnectionState('failed')
        if (error instanceof ApiError) throw error
        throw new Error('Your browser could not reach the backend. Check https://localhost:8012/health in this browser, then retry. If it shows a certificate warning, trust the local certificate first.')
      }
      setConnectionState('ready')
    }
    window.location.assign(`${API}/auth/salesforce?return_to=${encodeURIComponent(window.location.origin)}`)
  })
  const hasFilters = Boolean(query || status || priority || owner || reason)
  const clearFilters = () => { setQuery(''); setStatus(''); setPriority(''); setOwner(''); setReason('') }
  const presentAction = async (name: string, action: () => Promise<void>) => {
    setActiveAction(name)
    await run(action)
    setActiveAction('')
  }
  return <div className="app-shell">
    <a className="skip-link" href={page === 'progress' ? '#progress-content' : '#case-workspace'}>Skip to workspace</a>
    <nav className="topbar" aria-label="Workspace navigation">
      <a className="brand" href="#"><span className="brand-mark"><Icon name="layers" /></span><span>SUPPORT OPERATIONS</span></a>
      <span className="topbar-divider" /><a className="workspace-tab" href="#/cases" aria-current={page === 'cases' ? 'page' : undefined}><Icon name="inbox" />Cases</a>
      <a className="workspace-tab" href="#/progress" aria-current={page === 'progress' ? 'page' : undefined}><Icon name="activity" />Track Progress</a>
      <span className="workspace-label"><Icon name="user" />{connection.connected ? connection.display_name || 'Salesforce user' : 'Agent workspace'}</span>
    </nav>
    <main className="dashboard">
      <header className="page-header">
        <div><div className="breadcrumb">Workspace <Icon name="chevron" /><span>{page === 'progress' ? 'Track progress' : 'Case management'}</span></div><h1>{page === 'progress' ? 'Track Progress' : 'Support Cases'}<span className="title-dot">.</span></h1><p className="page-description">{page === 'progress' ? 'See your completed resolutions and daily progress.' : 'Review cases, request guidance, and record your work.'}</p></div>
        <div className="import-area">
          <label className={`button button-secondary excel-upload ${busy || (!betaReady && !connection.connected) ? 'is-disabled' : ''}`}>
            <Icon name={activeAction === 'import' ? 'sync' : 'upload'} className={activeAction === 'import' ? 'spin' : ''} />
            {activeAction === 'import' ? 'Importing workbook...' : 'Upload Excel'}<span className="beta-tag">BETA</span>
            <input aria-label="Upload Excel beta workbook" disabled={busy || (!betaReady && !connection.connected)} type="file" accept=".xlsx" onChange={event => {
              const file = event.target.files?.[0]; event.target.value = ''; if (!file) return
              void presentAction('import', async () => { const result = await api<{ imported: number; skipped: string[] }>('/tickets/import/excel', { method: 'POST', body: file }); await refresh(); setNotice(`Imported ${result.imported} cases. ${result.skipped.join(' ')}`) })
            }} />
          </label>
          <span className="import-caption">No Salesforce connection needed</span>
        </div>
      </header>

      <section className="integration-panel" aria-label="Salesforce connection">
        <div className="integration-identity"><span className="integration-icon"><Icon name="cloud" /></span><div><div className="integration-title">Salesforce <span className={`connection-badge ${connection.connected ? 'is-connected' : ''}`}><span className="status-dot" />{connection.connected ? 'Connected' : 'Not connected'}</span></div><p>{connection.connected ? `Last synced: ${connection.last_synced_at ? new Date(connection.last_synced_at).toLocaleString() : 'Never'}` : 'Connect to load cases from the Roster support Queue list view.'}</p></div></div>
        {connection.connected ? <div className="integration-actions">
          <span className="roster-label">Roster support Queue</span>
          <button className="button button-primary" disabled={busy || rosterState === 'loading'} onClick={() => void presentAction('sync', refresh)}><Icon name="sync" className={rosterState === 'loading' ? 'spin' : ''} />{rosterState === 'loading' ? 'Loading cases...' : rosterState === 'error' ? 'Retry' : 'Refresh cases'}</button>
          <button className="button button-danger" disabled={busy || rosterState === 'loading'} onClick={() => void presentAction('disconnect', async () => { await api('/auth/salesforce/disconnect', { method: 'POST' }); clearPrivateData(); setConnection({ ...disconnected, configured: connection.configured }); await refresh(); setNotice('Salesforce disconnected. Excel beta remains available.') })}><Icon name="disconnect" />Disconnect</button>
        </div> : <button className="button button-primary" disabled={busy || connectionState === 'loading'} onClick={connectSalesforce}><Icon name="cloud" />{connectionState === 'loading' ? 'Checking connection...' : connectionState === 'failed' ? 'Retry Salesforce connection' : 'Connect Salesforce'}<Icon name="arrow" /></button>}
      </section>
      {connection.connected && <div className="roster-status" role={rosterState === 'error' ? 'alert' : 'status'}>
        {rosterState === 'loading' ? 'Loading Roster support Queue cases...' : rosterState === 'missing' ? <><strong>No queue found</strong><span>No accessible Case list view named ?Roster support Queue? was found.</span></> : rosterState === 'error' ? <><strong>Unable to load cases</strong><span>{rosterError}</span></> : rosterState === 'found' ? <><strong>{rosterCount ? `${rosterCount} cases` : 'No cases'}</strong><span>{rosterCount ? 'From the Roster support Queue list view. Excel cases are listed separately by source.' : 'The Roster support Queue list view has no cases.'}</span></> : null}
      </div>}
      {notice && <div className="notice" role="status"><Icon name="activity" /><p>{notice}</p><button className="icon-button" aria-label="Dismiss notification" onClick={() => setNotice('')}><Icon name="close" /></button></div>}
      <div className="beta-note"><Icon name="shield" /><span>{connection.connected ? 'New Excel imports are saved to your Salesforce identity. Earlier beta imports remain temporary.' : 'Excel beta works without Salesforce. Imports are temporary; connect Salesforce before importing to keep permanent progress.'}</span></div>
      {!betaReady && !connection.connected && <div className="connection-empty"><EmptyState icon="cloud" title="Your workspace is getting ready">Connect Salesforce or start a local beta session to begin reviewing cases.</EmptyState><button className="button button-secondary" disabled={busy} onClick={() => void run(refresh)}><Icon name="sync" />Retry local beta connection</button></div>}
      {page === 'progress' && <ProgressPage connected={connection.connected} api={api} onExpired={() => { clearPrivateData(); setConnection(disconnected) }} />}
      {page === 'cases' && (betaReady || connection.connected) && <>
        <section className="overview" aria-label="Case overview">
          <Summary icon="inbox" label="Total cases" value={tickets.length} note="In your workspace" />
          <Summary icon="file" label="Open" value={tickets.filter(ticket => ticket.status === 'open').length} note="Awaiting review" tone="blue" />
          <Summary icon="clock" label="In progress" value={tickets.filter(ticket => ticket.status === 'in_progress').length} note="Work underway" tone="amber" />
          <Summary icon="alert" label="Escalated" value={tickets.filter(ticket => ticket.status === 'escalated').length} note="Human attention needed" tone="rose" />
        </section>
        <section className="workspace" id="case-workspace" aria-label="Case workspace">
          <div className="workspace-heading"><div className="section-heading"><span className="section-icon"><Icon name="inbox" /></span><div><h2>Case workspace</h2><p>A clear view of every case. A focused next step.</p></div></div><span className="count-label">{tickets.length} {tickets.length === 1 ? 'case' : 'cases'}</span></div>
          <div className="filter-bar">
            <label className="search-control"><Icon name="search" /><input aria-label="Search cases" placeholder="Search cases, customers, or keywords..." value={query} onChange={event => setQuery(event.target.value)} />{query && <button className="icon-button" aria-label="Clear search" onClick={() => setQuery('')}><Icon name="close" /></button>}</label>
            <div className="filter-scroll">
              <Filter label="Local status" value={status} set={setStatus} values={values('status')} />
              <Filter label="Triage priority" value={priority} set={setPriority} values={values('priority')} />
              <Filter label="Owner" value={owner} set={setOwner} values={[...new Set(tickets.map(ticket => ticket.owner || ticket.salesforce_owner_id).filter((value): value is string => Boolean(value)))]} />
              <Filter label="Case reason" value={reason} set={setReason} values={values('case_reason')} />
            </div>
          </div>
          <div className="workspace-grid">
            <section className="case-list" aria-label="Cases">
              <div className="list-caption"><span>{hasFilters ? 'Filtered cases' : 'All cases'}<span className="small-count">{filtered.length}</span></span>{hasFilters ? <button className="text-button" onClick={clearFilters}><Icon name="close" />Clear filters</button> : <span className="list-hint">Select a case to review</span>}</div>
              {filtered.length ? <div className="case-table-wrap"><table className="case-table"><thead><tr><th>Case</th><th>Subject / customer</th><th>Priority</th><th>Status</th></tr></thead><tbody>
                {filtered.map(ticket => <tr key={ticket.id} className={selected?.id === ticket.id ? 'selected-row' : ''} onClick={() => setSelectedId(ticket.id)}>
                  <td><button className="case-number" aria-label={`Open case ${ticket.salesforce_case_number || ticket.id}: ${ticket.subject}`} aria-pressed={selected?.id === ticket.id} title={ticket.salesforce_case_number || ticket.id} onClick={() => setSelectedId(ticket.id)}>{ticket.salesforce_case_number || ticket.id}</button><span className="case-source">{ticket.salesforce_case_id ? 'Salesforce' : 'Excel / local'}</span></td>
                  <td><button className="case-subject" onClick={() => setSelectedId(ticket.id)}>{ticket.subject}</button><span className="case-customer">{ticket.customer}</span></td>
                  <td><Badge kind="priority" value={ticket.priority} /></td><td><Badge value={ticket.status} /></td>
                </tr>)}
              </tbody></table><div className="list-footer">Showing {filtered.length} of {tickets.length} cases<span>Local tracking status</span></div></div> : <div className="list-empty"><EmptyState icon={hasFilters ? 'search' : 'inbox'} title={hasFilters ? 'No matching cases' : connection.connected ? (rosterState === 'loading' ? 'Loading cases...' : rosterState === 'missing' ? 'No queue found' : rosterState === 'error' ? 'Unable to load cases' : 'No cases') : 'A fresh start for your queue'}>{hasFilters ? 'Try a different search or clear your filters to see more cases.' : connection.connected ? 'Use Refresh cases to check the Roster support Queue list view again, or upload an Excel workbook.' : 'Upload an Excel workbook or connect Salesforce. Your cases will appear here.'}</EmptyState>{hasFilters && <button className="button button-secondary" onClick={clearFilters}>Clear all filters</button>}</div>}
            </section>
            {selected ? <CaseDetails key={selected.id} ticket={selected} busy={busy} canAssign={connection.can_assign} run={run} update={update} /> : <aside className="details-empty"><EmptyState icon="file" title="Your next step starts here">Select a case to explore its details, request handling guidance, and record your work.</EmptyState><div className="empty-capabilities"><span><Icon name="sparkles" />Clear handling guidance</span><span><Icon name="shield" />Human-reviewed actions</span></div></aside>}
          </div>
        </section>
        <section className="performance-panel" aria-label="My activity"><div className="section-heading"><span className="section-icon"><Icon name="activity" /></span><div><h2>My activity</h2><p>Your work, in view.</p></div></div><div className="performance-members">{performance.length ? performance.map(member => <div className="performance-member" key={member.id}><div className="member-identity"><span className="avatar"><Icon name="user" /></span><span title={member.name}>{member.name}</span></div><div className="performance-stats"><span><strong>{member.cases_touched}</strong>Cases touched</span><span><strong>{member.case_updates}</strong>Case updates</span><span><strong>{member.suggestions_requested}</strong>Suggestions requested</span></div></div>) : <p className="muted">Your case activity will appear as you work.</p>}</div></section>
      </>}
      <footer className="page-footer"><span><Icon name="layers" />Support Operations</span><span>Thoughtful guidance. Human decisions.</span></footer>
    </main>
  </div>
}

function Summary({ icon, label, value, note, tone = 'indigo' }: { icon: 'inbox' | 'file' | 'clock' | 'alert'; label: string; value: number; note: string; tone?: string }) {
  return <div className="summary-card"><div className="summary-copy"><span>{label}</span><strong>{value.toLocaleString()}</strong><small>{note}</small></div><span className={`summary-icon tone-${tone}`}><Icon name={icon} /></span></div>
}

function Filter({ label, value, set, values }: { label: string; value: string; set: (value: string) => void; values: string[] }) {
  return <select className="filter-select" aria-label={label} value={value} onChange={event => set(event.target.value)}><option value="">{label}</option>{values.map(item => <option key={item} value={item}>{humanize(item)}</option>)}</select>
}

function CaseDetails({ ticket, busy, canAssign, run, update }: { ticket: Ticket & StructuredGuidance; busy: boolean; canAssign: boolean; run: (action: () => Promise<void>) => Promise<void>; update: (path: string, options: RequestInit) => Promise<void> }) {
  const isSalesforce = ticket.source === 'salesforce'
  const [sfOptions, setSfOptions] = useState<{ enabled: boolean; statuses: { value: string; label: string }[]; can_edit_status: boolean; can_edit_owner: boolean } | null>(null)
  const [sfError, setSfError] = useState(''), [saveNotice, setSaveNotice] = useState('')
  const [status, setStatus] = useState(isSalesforce ? ticket.salesforce_status ?? '' : ticket.status), [owner, setOwner] = useState(isSalesforce ? ticket.salesforce_owner_id ?? '' : ticket.owner ?? ''), [note, setNote] = useState(ticket.resolution_note ?? '')
  const [notes, setNotes] = useState('')
  const [analyzing, setAnalyzing] = useState(false), [saving, setSaving] = useState(false), [assigning, setAssigning] = useState(false)
  useEffect(() => { setStatus(isSalesforce ? ticket.salesforce_status ?? '' : ticket.status); setOwner(isSalesforce ? ticket.salesforce_owner_id ?? '' : ticket.owner ?? ''); setNote(ticket.resolution_note ?? '') }, [isSalesforce, ticket.status, ticket.salesforce_status, ticket.owner, ticket.salesforce_owner_id, ticket.resolution_note])
  useEffect(() => {
    let active = true
    setSfOptions(null); setSfError(''); setSaveNotice('')
    if (isSalesforce) api<NonNullable<typeof sfOptions>>(`/tickets/${ticket.id}/salesforce-edit-options`).then(value => { if (active) setSfOptions(value) }).catch(error => { if (active) setSfError(error instanceof Error ? error.message : 'Unable to load Salesforce editing options.') })
    return () => { active = false }
  }, [ticket.id, isSalesforce])
  const needsApproval = Boolean(ticket.suggested_approach) && (['high', 'critical'].includes(ticket.priority) || /controlled action|written authorization|employee must approve|explicit confirmation/i.test(`${ticket.rationale || ''} ${ticket.suggested_approach}`))
  const requestGuidance = async () => {
    setAnalyzing(true)
    try { await run(() => update(`/tickets/${ticket.id}/suggest-approach`, json({ agent_notes: notes || null }))) }
    finally { setAnalyzing(false) }
  }
  const actions: Record<string, string> = { requested_suggestion: 'Requested AI handling suggestion', updated_case: 'Updated local case details', saved_salesforce: 'Saved changes to Salesforce' }
  const modelGuidance = ['gemini_rag_refined', 'openai_rag_refined'].includes(ticket.ai_mode || '')
  return <aside className="case-details" aria-label="Selected case details">
    <div className="detail-header"><div className="detail-topline"><span className="detail-kicker"><Icon name="file" />CASE DETAILS</span><Badge value={ticket.status} /></div><h2>{ticket.subject}</h2><div className="detail-subtitle"><span className="detail-id" title={ticket.id}>{ticket.salesforce_case_number || ticket.id}</span><span className="detail-divider">/</span><Badge kind="priority" value={ticket.priority} /></div></div>
    <div className="detail-body">
      <section className="detail-section metadata-section"><div className="section-title"><Icon name="file" /><h3>Case information</h3><span className="source-tag">{ticket.salesforce_case_id ? 'Salesforce' : 'Local case'}</span></div>
        <dl className="metadata-grid"><div><dt>Customer</dt><dd>{ticket.customer || 'Not provided'}</dd></div><div><dt>Case reason</dt><dd>{ticket.case_reason || 'Not specified'}</dd></div>
          {ticket.salesforce_case_id && <><div><dt>Salesforce status</dt><dd>{ticket.salesforce_status || 'Not specified'}</dd></div><div><dt>Salesforce priority</dt><dd>{ticket.salesforce_priority || 'Not specified'}</dd></div><div className="metadata-full"><dt>Salesforce owner</dt><dd>{ticket.salesforce_owner_id || 'Unassigned'}</dd></div></>}
        </dl>
        <div className="case-description"><span className="field-caption">Description</span><p>{ticket.description_missing || !ticket.message ? "No description supplied. Guidance will request clarification." : ticket.message}</p></div>
        {ticket.imported_case_fields && Object.keys(ticket.imported_case_fields).length > 0 && <details className="imported-metadata"><summary><Icon name="layers" />Imported case metadata<Icon name="chevron" /></summary><dl className="metadata-grid">{Object.entries(ticket.imported_case_fields).map(([field, value]) => <div key={field}><dt>{field}</dt><dd>{value}</dd></div>)}</dl></details>}
        {ticket.salesforce_case_id && canAssign && <button className="button button-secondary full-width" disabled={busy} onClick={() => { setAssigning(true); void run(() => update(`/cases/${ticket.salesforce_case_id}/assign-me`, { method: 'POST' })).finally(() => setAssigning(false)) }}><Icon name="user" />{assigning ? 'Assigning...' : 'Assign to Me in Salesforce'}</button>}
      </section>

      <section className="detail-section handling-section"><div className="section-title"><span className="guidance-icon"><Icon name="sparkles" /></span><h3>Handling guidance</h3><span className="assist-label">AGENT ASSIST</span></div><p className="section-description">A grounded approach, ready for your review.</p>
        <label className="form-field" htmlFor="refinement-notes"><span>Refinement notes<span className="optional">Optional</span></span><textarea id="refinement-notes" maxLength={2000} value={notes} onChange={event => setNotes(event.target.value)} placeholder="Add context or a specific question for this case..." /></label>
        <button className="button button-guidance full-width" disabled={busy} aria-busy={analyzing} onClick={() => void requestGuidance()}><Icon name={analyzing ? 'sync' : 'sparkles'} className={analyzing ? 'spin' : ''} />{analyzing ? 'Analyzing case...' : 'Suggest me the approach'}{!analyzing && <Icon name="arrow" />}</button>
        <div className="guidance-output" aria-live="polite" aria-busy={analyzing}>
          {analyzing ? <div className="guidance-loading" role="status"><div className="loading-title"><Icon name="sparkles" /><span>Analyzing case...</span></div><p>Reviewing case context and relevant playbooks.</p><div className="skeleton-line" /><div className="skeleton-line" /><div className="skeleton-line short" /></div> : ticket.suggested_approach ? <div className="suggestion-card">
            <div className="suggestion-heading"><span className="suggestion-mark"><Icon name="sparkles" /></span><div><h4>{modelGuidance ? 'AI Handling Suggestion' : 'Handling Suggestion'}</h4><p>{modelGuidance ? 'Concise guidance for your review' : 'Next steps for your review'}</p></div><span className="guidance-badge">{modelGuidance ? 'AI GUIDANCE' : 'GUIDANCE'}</span></div>
            {ticket.case_summary && ticket.response_type !== 'answer' && <div className="guidance-summary"><span className="field-caption">Case interpretation</span><p>{visibleGuidanceText(ticket.case_summary)}</p></div>}
            {!!ticket.answer_bullets?.length && <div className="guidance-block"><span className="field-caption">Answer</span><GuidanceBullets items={ticket.answer_bullets} /></div>}
            {!!ticket.agent_steps?.length && <div className="guidance-block"><span className="field-caption">Agent steps</span><GuidanceBullets items={ticket.agent_steps} ordered /></div>}
            {!ticket.answer_bullets?.length && !ticket.agent_steps?.length && <SavedGuidance text={ticket.suggested_approach} />}
            {!!ticket.mandatory_constraints?.length && <div className="guidance-missing guidance-checks"><span className="field-caption">Required checks</span><ul>{ticket.mandatory_constraints.map((item, index) => <li key={index}>{visibleGuidanceText(item)}</li>)}</ul></div>}
            {!!ticket.missing_information?.length && <div className="guidance-missing"><span className="field-caption">Details to confirm</span><ul>{ticket.missing_information.map((item, index) => <li key={index}>{visibleGuidanceText(item)}</li>)}</ul></div>}
            {needsApproval ? <div className="approval-warning"><Icon name="alert" /><div><strong>Approval Required</strong><p>This action requires employee authorization before execution. Follow all approval and escalation requirements in the guidance.</p></div></div> : ticket.requires_human && <div className="review-note"><Icon name="shield" /><span>Employee review required before taking action.</span></div>}
            {ticket.ai_advisory_priority && <div className="advisory-priority"><span>AI advisory priority</span><Badge kind="priority" value={ticket.ai_advisory_priority} /></div>}
          </div> : <div className="guidance-empty"><Icon name="sparkles" /><p>Your guidance will appear here.<span>Request an approach when you're ready.</span></p></div>}
        </div>
        {ticket.guidance_stale && <p role="status" className="review-note">The case description changed. Request updated guidance.</p>}
        {ticket.reply_available === false && ticket.suggested_approach && <p className="review-note">Customer drafting is unavailable. Ask an experienced agent to review the case before preparing a reply.</p>}
        {ticket.reply_draft && ticket.reply_available !== false && <div className="reply-draft"><span className="field-caption">Customer reply draft</span><p className="muted">Review the wording and case details before copying and sending.</p><GuidanceText text={ticket.reply_draft} /><details><summary>Exact text to copy</summary><textarea aria-label="Customer reply draft" readOnly value={ticket.reply_draft} /></details><button className="button button-secondary" disabled={busy} onClick={() => void run(async () => { await navigator.clipboard.writeText(ticket.reply_draft || '') })}>Copy draft</button></div>}
      </section>

      <section className="detail-section tracking-section"><div className="section-title"><Icon name="layers" /><h3>{isSalesforce ? 'Salesforce case editing' : 'Local case tracking'}</h3><span className="source-tag">{isSalesforce ? 'SALESFORCE' : 'LOCAL'}</span></div><p className="section-description">{isSalesforce ? 'Save updates the Salesforce status and owner. Changed notes are added as internal Case Comments.' : 'These notes and status changes are saved in this dashboard.'}</p>
        <div className="tracking-grid"><label className="form-field" htmlFor="local-status"><span>Status</span><select id="local-status" disabled={isSalesforce && !sfOptions?.can_edit_status} value={status} onChange={event => setStatus(event.target.value)}>{isSalesforce ? <>{!sfOptions?.statuses.some(item => item.value === status) && <option value={status}>{status || 'Loading...'}</option>}{sfOptions?.statuses.map(item => <option key={item.value} value={item.value}>{item.label}</option>)}</> : ['open', 'in_progress', 'resolved', 'escalated'].map(value => <option key={value} value={value}>{humanize(value)}</option>)}</select></label><label className="form-field" htmlFor="local-owner"><span>{isSalesforce ? 'Owner (Salesforce user or queue ID)' : 'Owner'}</span><input id="local-owner" disabled={isSalesforce && !sfOptions?.can_edit_owner} maxLength={isSalesforce ? 18 : 80} value={owner} onChange={event => setOwner(event.target.value)} placeholder="Assign an owner" /></label></div>
        <label className="form-field" htmlFor="resolution-note"><span>{isSalesforce ? 'Internal Case Comment' : 'Resolution note'}</span><textarea id="resolution-note" maxLength={3000} value={note} onChange={event => setNote(event.target.value)} placeholder="Record findings, progress, or next steps..." /></label>
        {isSalesforce && (sfError || (sfOptions && !sfOptions.enabled)) && <p role="alert">{sfError || 'Salesforce saving is disabled on this server.'}</p>}
        {saveNotice && <p role="status">{saveNotice}</p>}
        <div className="tracking-footer"><span><Icon name="shield" />{isSalesforce ? 'Saves directly to Salesforce' : 'Saved to this workspace'}</span><button className="button button-primary" disabled={busy || (isSalesforce && !sfOptions?.enabled)} onClick={() => {
          setSaving(true); setSaveNotice('')
          void run(async () => {
            await update(isSalesforce ? `/tickets/${ticket.id}/save-salesforce` : `/tickets/${ticket.id}`, json({ status, owner, resolution_note: note }, isSalesforce ? 'POST' : 'PATCH'))
            setSaveNotice(isSalesforce ? 'Saved to Salesforce.' : 'Saved locally.')
          }).finally(() => setSaving(false))
        }}><Icon name={saving ? 'sync' : 'save'} className={saving ? 'spin' : ''} />{saving ? 'Saving...' : isSalesforce ? 'Save to Salesforce' : 'Save local changes'}</button></div>
      </section>

      <section className="detail-section activity-section"><div className="section-title"><Icon name="activity" /><h3>Case activity</h3><span className="small-count">{ticket.activity?.length ?? 0}</span></div>
        {ticket.activity?.length ? <ol className="activity-timeline">{ticket.activity.map((entry, index) => <li key={index}><span className={`timeline-marker ${entry.action === 'requested_suggestion' ? 'timeline-ai' : ''}`}><Icon name={entry.action === 'requested_suggestion' ? 'sparkles' : 'check'} /></span><div className="timeline-content"><time dateTime={entry.at} title={new Date(entry.at).toLocaleString()}>{new Date(entry.at).toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })}<span>{new Date(entry.at).toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })}</span></time><strong>{entry.member_name}</strong><p>{actions[entry.action] || humanize(entry.action)}</p></div></li>)}</ol> : <EmptyState icon="clock" title="The story starts with you" compact>Requests and case updates will appear here as you work.</EmptyState>}
      </section>
    </div>
  </aside>
}
export default App
