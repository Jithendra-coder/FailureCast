# Shared layouts

App owns the application shell, persistent navigation, top bar, mobile navigation, auth and offline states, notification toast, and all route screen components. There are no other local UI imports.

## frontend/src/App.tsx — complete source

```tsx
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowRight, Boxes, Check,
  ChevronDown, CircleHelp, Clock3, Cpu, Database, Download, Gauge, GitBranch,
  Layers3, LineChart as LineIcon, LockKeyhole, LogOut, Menu, Pause, Play, RotateCcw, Settings2,
  ShieldCheck, Sparkles, UploadCloud, Waves, X, Zap,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'

type Screen = 'overview' | 'dataset' | 'engine' | 'replay' | 'experiments' | 'explain' | 'monitoring' | 'registry'
type ApiData = { [key: string]: any }
const screens: { id: Screen; label: string; icon: typeof Activity; section: string }[] = [
  { id: 'overview', label: 'Overview', icon: Gauge, section: 'WORKSPACE' },
  { id: 'engine', label: 'Engine health', icon: Activity, section: 'WORKSPACE' },
  { id: 'replay', label: 'Live replay', icon: Waves, section: 'WORKSPACE' },
  { id: 'dataset', label: 'Dataset explorer', icon: Database, section: 'INTELLIGENCE' },
  { id: 'experiments', label: 'Experiments', icon: LineIcon, section: 'INTELLIGENCE' },
  { id: 'explain', label: 'Explainability', icon: Sparkles, section: 'INTELLIGENCE' },
  { id: 'monitoring', label: 'Monitoring', icon: GitBranch, section: 'CONTROL ROOM' },
  { id: 'registry', label: 'Model registry', icon: Boxes, section: 'CONTROL ROOM' },
]

async function api(path: string, init?: RequestInit): Promise<any> {
  const response = await fetch(`/api/v1${path}`, { credentials: 'include', ...init })
  const payload = await response.json().catch(() => ({}))
  if (response.status === 401 && !path.startsWith('/auth/')) window.dispatchEvent(new Event('failurecast:unauthorized'))
  if (!response.ok) throw new Error(payload.detail || `Request failed (${response.status})`)
  return payload
}

const number = (value: number | undefined, digits = 0) => value == null || Number.isNaN(value) ? '—' : value.toLocaleString(undefined, { maximumFractionDigits: digits })
const severityLabel = (value = 'normal') => value === 'critical' ? 'Critical' : value === 'warning' ? 'Warning' : value === 'watch' ? 'Watch' : 'Normal'

function Badge({ tone = 'neutral', children, dot = false }: { tone?: string; children: ReactNode; dot?: boolean }) {
  return <span className={`badge ${tone}`}>{dot && <i />} {children}</span>
}

function CardTitle({ title, detail, action }: { title: string; detail?: string; action?: ReactNode }) {
  return <div className="card-title"><div><h3>{title}</h3>{detail && <p>{detail}</p>}</div>{action}</div>
}

function App() {
  const [authStatus, setAuthStatus] = useState<'checking' | 'login' | 'ready'>('checking')
  const [authRequired, setAuthRequired] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [signingIn, setSigningIn] = useState(false)
  const [screen, setScreen] = useState<Screen>('overview')
  const [overview, setOverview] = useState<ApiData | null>(null)
  const [engines, setEngines] = useState<ApiData[]>([])
  const [datasets, setDatasets] = useState<ApiData[]>([])
  const [models, setModels] = useState<ApiData[]>([])
  const [jobs, setJobs] = useState<ApiData[]>([])
  const [alerts, setAlerts] = useState<ApiData[]>([])
  const [drift, setDrift] = useState<ApiData | null>(null)
  const [explanation, setExplanation] = useState<ApiData | null>(null)
  const [selectedEngine, setSelectedEngine] = useState('')
  const [connection, setConnection] = useState<'loading' | 'online' | 'offline'>('loading')
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [replay, setReplay] = useState<ApiData | null>(null)
  const [replaySeries, setReplaySeries] = useState<ApiData[]>([])
  const [replaySpeed, setReplaySpeed] = useState(1)
  const [importFiles, setImportFiles] = useState<FileList | null>(null)
  const [subset, setSubset] = useState('FD001')
  const [algorithm, setAlgorithm] = useState('HistGradientBoostingRegressor')
  const [uploading, setUploading] = useState(false)
  const [training, setTraining] = useState(false)
  const [filePickerKey, setFilePickerKey] = useState(0)
  const [mobileNav, setMobileNav] = useState(false)

  const refresh = useCallback(async (showLoading = false) => {
    if (showLoading) setBusy(true)
    try {
      const [o, e, d, m, j, a, r] = await Promise.all([
        api('/overview'), api('/engines'), api('/datasets'), api('/models'), api('/training/jobs'), api('/alerts'), api('/replay/sessions'),
      ])
      setOverview(o); setEngines(e.items); setDatasets(d.items); setModels(m.items); setJobs(j.items); setAlerts(a.items)
      const previousReplay = r.items.find((item: ApiData) => item.status === 'running' || item.status === 'paused')
      setReplay((current) => current || previousReplay || null)
      if (previousReplay?.latest) setReplaySeries((current) => current.length ? current : [previousReplay.latest])
      setSelectedEngine((current) => current || o.selected_engine || e.items[0]?.id || '')
      setConnection('online')
    } catch {
      setConnection('offline')
    } finally {
      if (showLoading) setBusy(false)
    }
  }, [])

  useEffect(() => {
    let current = true
    fetch('/api/v1/auth/session', { credentials: 'include' })
      .then(async (response) => {
        if (!response.ok) throw new Error('Session check failed.')
        return response.json()
      })
      .then((session) => { if (current) { setAuthRequired(session.required); setAuthStatus(session.required && !session.authenticated ? 'login' : 'ready') } })
      .catch(() => { if (current) setAuthStatus('ready') })
    const onUnauthorized = () => { setAuthStatus('login'); setOverview(null); setEngines([]); setModels([]); setReplay(null); setReplaySeries([]) }
    window.addEventListener('failurecast:unauthorized', onUnauthorized)
    return () => { current = false; window.removeEventListener('failurecast:unauthorized', onUnauthorized) }
  }, [])

  useEffect(() => {
    if (authStatus !== 'ready') return
    void refresh(true)
    const timer = window.setInterval(() => void refresh(), 12000)
    return () => window.clearInterval(timer)
  }, [authStatus, refresh])

  useEffect(() => {
    if (!notice) return
    const timer = window.setTimeout(() => setNotice(''), 3600)
    return () => window.clearTimeout(timer)
  }, [notice])

  useEffect(() => {
    if (screen === 'monitoring') void api('/monitoring/drift').then(setDrift).catch((error) => setNotice(error.message))
    if (screen === 'explain' && selectedEngine) void api(`/explain/${selectedEngine}`).then(setExplanation).catch((error) => setNotice(error.message))
  }, [screen, selectedEngine, overview?.model?.id])

  useEffect(() => {
    if (!replay?.id || replay.status !== 'running') return
    const timer = window.setInterval(async () => {
      try {
        const next = await api(`/replay/${replay.id}/step`, { method: 'POST' })
        setReplay(next)
        if (next.latest) setReplaySeries((items) => [...items.slice(-39), next.latest])
      } catch (error) { setNotice((error as Error).message) }
    }, Math.max(220, 1100 / replaySpeed))
    return () => window.clearInterval(timer)
  }, [replay?.id, replay?.status, replaySpeed])

  const selected = useMemo(() => engines.find((item) => item.id === selectedEngine) || engines[0], [engines, selectedEngine])
  const navSections = [...new Set(screens.map((item) => item.section))]

  const perform = async (operation: () => Promise<unknown>, success: string) => {
    try { await operation(); setNotice(success); await refresh() }
    catch (error) { setNotice((error as Error).message) }
  }

  const signIn = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault(); setSigningIn(true); setAuthError('')
    try {
      await api('/auth/login', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ password }) })
      setPassword(''); setAuthStatus('ready')
    } catch (error) { setAuthError((error as Error).message) }
    finally { setSigningIn(false) }
  }
  const signOut = async () => {
    try { await api('/auth/logout', { method: 'POST' }) } catch { /* The browser drops an expired session on reload. */ }
    setAuthStatus('login'); setOverview(null); setEngines([]); setDatasets([]); setModels([]); setJobs([]); setAlerts([]); setReplay(null); setReplaySeries([])
  }

  const acknowledge = (id: string) => perform(() => api(`/alerts/${id}/acknowledge`, { method: 'POST' }), 'Alert acknowledged.')
  const train = async () => {
    setTraining(true)
    try {
      await perform(async () => {
        const job = await api('/training/jobs', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ algorithm }) })
        setScreen('experiments')
        return job
      }, 'Training job queued. It will register as a candidate when validation completes.')
    } finally { setTraining(false) }
  }
  const startReplay = async () => {
    if (!selectedEngine) return
    try {
      const session = await api('/replay/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_id: selectedEngine, speed: replaySpeed }) })
      setReplay(session); setReplaySeries([]); setNotice('Historical sensor replay started.')
      setScreen('replay')
    } catch (error) { setNotice((error as Error).message) }
  }
  const replayAction = async (action: string) => {
    if (!replay) return
    try {
      const next = await api(`/replay/${replay.id}/${action}`, { method: 'POST' })
      setReplay(next)
      if (action === 'reset') setReplaySeries([])
      else if (action === 'step' && next.latest) setReplaySeries((items) => [...items.slice(-39), next.latest])
    } catch (error) { setNotice((error as Error).message) }
  }
  const importDataset = async () => {
    if (!importFiles?.length) { setNotice('Choose the train, test and RUL files first.'); return }
    const form = new FormData()
    for (const file of Array.from(importFiles)) form.append('files', file)
    form.append('subset', subset)
    setUploading(true)
    try {
      const result = await api('/datasets/import', { method: 'POST', body: form })
      setNotice(result.reused ? 'Existing dataset version selected.' : 'Dataset validated and imported.')
      setImportFiles(null)
      setFilePickerKey((key) => key + 1)
      await refresh()
    } catch (error) { setNotice((error as Error).message) }
    finally { setUploading(false) }
  }

  const nav = <>
    <div className="brand"><div className="brand-mark"><Activity size={19} strokeWidth={2.5} /></div><div><b>failurecast</b><span>RELIABILITY INTELLIGENCE</span></div></div>
    <div className="workspace-switch"><div className="workspace-icon">N</div><div><b>Northstar Systems</b><span>Research workspace</span></div><ChevronDown size={15} /></div>
    <nav className="side-nav" aria-label="Main navigation">
      {navSections.map((section) => <div key={section} className="nav-section"><span className="nav-caption">{section}</span>{screens.filter((item) => item.section === section).map(({ id, label, icon: Icon }) => <button key={id} className={`nav-item ${screen === id ? 'active' : ''}`} onClick={() => { setScreen(id); setMobileNav(false) }}><Icon size={17} strokeWidth={1.8} /><span>{label}</span>{id === 'overview' && !!overview?.summary?.open_alerts && <i className="nav-count">{overview.summary.open_alerts}</i>}</button>)}</div>)}
    </nav>
    <div className="side-bottom"><div className="plan-card"><div className="plan-icon"><ShieldCheck size={17} /></div><div><b>Research mode</b><span>Local data workspace</span></div><span className="plan-live" /></div><button className="nav-item side-setting" onClick={() => setNotice('Alert thresholds: watch 60 · warning 30 · critical 15 cycles.')}><Settings2 size={17} /><span>Workspace settings</span></button><div className="profile-row"><div className="avatar">FC</div><div><b>{authRequired ? 'Workspace admin' : 'Local workspace'}</b><span>{authRequired ? 'Single administrator' : 'Authentication disabled'}</span></div>{authRequired && <button className="icon-button signout-button" onClick={signOut} title="Sign out" aria-label="Sign out"><LogOut size={15} /></button>}</div></div>
  </>

  if (authStatus === 'checking') return <div className="auth-screen"><div className="auth-card"><div className="brand-mark large"><Activity size={24} /></div><span className="eyebrow">FAILURECAST · SECURE WORKSPACE</span><div className="loader" aria-label="Checking session" /></div></div>
  if (authStatus === 'login') return <main className="auth-screen"><form className="auth-card" onSubmit={signIn}><div className="brand-mark large"><Activity size={24} /></div><span className="eyebrow">FAILURECAST · SECURE WORKSPACE</span><div><h1>Welcome back</h1><p>Sign in with the workspace administrator password.</p></div><label htmlFor="admin-password">Administrator password</label><input id="admin-password" type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} required maxLength={256} autoFocus /><p className="auth-error" role="alert">{authError}</p><button className="primary-button" type="submit" disabled={signingIn || !password}><LockKeyhole size={15} />{signingIn ? 'Signing in…' : 'Sign in'}</button><small>Research workspace · No equipment control</small></form></main>

  if (connection === 'offline') return <div className="offline"><div className="offline-card"><div className="brand-mark large"><Activity size={24} /></div><p className="eyebrow">FAILURECAST · LOCAL WORKSPACE</p><h1>The API service is unavailable.</h1><p>Check the service health, then retry to reconnect to your reliability workspace.</p><button className="primary-button" onClick={() => void refresh(true)}>Retry connection <ArrowRight size={16} /></button></div></div>

  return <div className="app-shell">
    <aside className={`sidebar ${mobileNav ? 'mobile-open' : ''}`}>{nav}</aside>
    {mobileNav && <button className="scrim" onClick={() => setMobileNav(false)} aria-label="Close navigation" />}
    <main className="main-area">
      <header className="topbar"><button className="mobile-menu icon-button" onClick={() => setMobileNav(true)} aria-label="Open navigation"><Menu size={19} /></button><div className="breadcrumbs"><span>Workspace</span><b>/</b><strong>{screens.find((item) => item.id === screen)?.label}</strong></div><div className="topbar-actions"><span className="data-chip"><i />{overview?.dataset?.subset || 'FD001'} <span>·</span> {overview?.simulation_only ? 'SIMULATED' : 'DATASET'}</span><button className="icon-button" title="This is a research demonstration, not an operational maintenance system." onClick={() => setNotice('FailureCast estimates are research outputs, not guaranteed service life or maintenance instructions.')}><CircleHelp size={17} /></button><div className="top-divider" /><div className="connection"><i className="online-dot" /> API connected</div></div></header>
      <div className="page-wrap">
        {connection === 'loading' && !overview ? <div className="loading"><div className="loader" /><span>Preparing reliability workspace…</span></div> : <>
          {screen === 'overview' && overview && <Overview data={overview} engines={engines} alerts={alerts} setScreen={setScreen} selectEngine={setSelectedEngine} acknowledge={acknowledge} startReplay={startReplay} />}
          {screen === 'engine' && <EngineScreen engine={selected} engines={engines} selectedId={selectedEngine} setSelected={setSelectedEngine} startReplay={startReplay} />}
          {screen === 'replay' && <ReplayScreen engines={engines} selectedEngine={selectedEngine} setSelected={setSelectedEngine} replay={replay} series={replaySeries} speed={replaySpeed} setSpeed={setReplaySpeed} start={startReplay} action={replayAction} />}
          {screen === 'dataset' && <DatasetScreen datasets={datasets} active={overview?.dataset} files={importFiles} setFiles={setImportFiles} filePickerKey={filePickerKey} subset={subset} setSubset={setSubset} upload={importDataset} uploading={uploading} />}
          {screen === 'experiments' && <ExperimentsScreen models={models} jobs={jobs} algorithm={algorithm} setAlgorithm={setAlgorithm} train={train} busy={busy || training} />}
          {screen === 'explain' && <ExplainScreen engine={selected} engines={engines} selectedId={selectedEngine} setSelected={setSelectedEngine} explanation={explanation} />}
          {screen === 'monitoring' && <MonitoringScreen drift={drift} model={models.find((item) => item.status === 'active')?.id} setScreen={setScreen} announce={setNotice} refresh={() => api('/monitoring/drift').then(setDrift).catch((error) => setNotice(error.message))} />}
          {screen === 'registry' && <RegistryScreen models={models} refresh={refresh} announce={setNotice} />}
          <footer className="page-footer"><span>FailureCast <b>·</b> Predictive maintenance research platform</span><span>Simulation only · No equipment control</span></footer>
        </>}
      </div>
    </main>
    {notice && <div className="toast" role="status"><span className="toast-mark"><Check size={14} /></span>{notice}<button onClick={() => setNotice('')} aria-label="Dismiss"><X size={15} /></button></div>}
  </div>
}

function PageHeading({ eyebrow, title, detail, action, tag }: { eyebrow: string; title: string; detail: string; action?: ReactNode; tag?: ReactNode }) {
  return <div className="page-heading"><div><div className="eyebrow-row"><span className="eyebrow">{eyebrow}</span>{tag}</div><h1>{title}</h1><p>{detail}</p></div>{action && <div className="heading-action">{action}</div>}</div>
}

function MetricCard({ label, value, suffix, note, tone = 'blue', icon: Icon, trend }: { label: string; value: string | number; suffix?: string; note: string; tone?: string; icon: typeof Activity; trend?: string }) {
  return <div className="metric-card"><div className={`metric-icon ${tone}`}><Icon size={18} /></div><span className="metric-label">{label}</span><div className="metric-value">{value}<small>{suffix}</small></div><div className="metric-note"><span>{trend && <ArrowDownRight size={13} />}{trend}</span>{note}</div></div>
}

function Overview({ data, engines, alerts, setScreen, selectEngine, acknowledge, startReplay }: any) {
  const metrics = data.model?.metrics || {}
  const recent = alerts.slice(0, 4)
  const exportReport = () => {
    const file = new Blob([JSON.stringify({ generated_at: new Date().toISOString(), dataset: data.dataset, model: data.model, summary: data.summary, alerts }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(file); const link = document.createElement('a'); link.href = url; link.download = 'failurecast-evaluation-summary.json'; link.click(); URL.revokeObjectURL(url)
  }
  return <>
    <PageHeading eyebrow="OPERATIONS · OVERVIEW" title="Fleet intelligence" detail="A clear view of engine health, model performance and the signals that need attention." tag={data.simulation_only && <Badge tone="demo">SIMULATED DATA</Badge>} action={<><button className="secondary-button" onClick={exportReport}><Download size={15} /> Export report</button><button className="primary-button" onClick={startReplay}><Play size={15} fill="currentColor" /> Start replay</button></>} />
    <div className="metric-grid">
      <MetricCard label="Engines monitored" value={number(data.summary?.engines)} note="in selected dataset" icon={Cpu} tone="violet" />
      <MetricCard label="Median remaining life" value={number(data.summary?.median_rul, 1)} suffix="cycles" note="model-estimated · not guaranteed" icon={Gauge} tone="blue" />
      <MetricCard label="Needs attention" value={number(data.summary?.watch + data.summary?.critical)} note={`${data.summary?.critical || 0} critical · ${data.summary?.watch || 0} watch`} icon={AlertTriangle} tone="amber" trend={data.summary?.critical ? 'Review now' : ''} />
      <MetricCard label="Validation MAE" value={number(metrics.mae, 1)} suffix="cycles" note={`${data.model?.algorithm || 'Model'} · engine holdout`} icon={LineIcon} tone="green" />
    </div>
    <div className="content-grid main-grid">
      <section className="panel chart-panel"><CardTitle title="Remaining useful life" detail="Observed labels and model estimates across a representative engine trajectory." action={<span className="subtle-select">{data.selected_engine} <ChevronDown size={14} /></span>} />
        <div className="chart-legend"><span><i className="legend-blue" /> Model estimate</span><span><i className="legend-gray" /> Observed label</span><span className="chart-period">CYCLE BY CYCLE</span></div>
        <div className="hero-chart"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.series} margin={{ top: 12, right: 5, left: -18, bottom: 0 }}><defs><linearGradient id="rulFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#477de3" stopOpacity={0.18} /><stop offset="92%" stopColor="#477de3" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#edf0f3" vertical={false} /><XAxis dataKey="cycle" tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} tickMargin={11} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} tickMargin={8} /><Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e8ecf0', boxShadow: '0 8px 24px #15233712', fontSize: 12 }} /><Area type="monotone" dataKey="predicted_rul" stroke="#4d7de0" strokeWidth={2.5} fill="url(#rulFill)" dot={false} activeDot={{ r: 4, strokeWidth: 2 }} name="Model estimate" /><Line type="monotone" dataKey="actual_rul" stroke="#9aa5b2" strokeWidth={1.6} strokeDasharray="4 5" dot={false} name="Observed label" connectNulls={false} /></AreaChart></ResponsiveContainer></div>
        <div className="chart-foot"><span><i className="green-dot" /> Last data point received <b>·</b> cycle {data.series?.at(-1)?.cycle}</span><button className="text-button" onClick={() => setScreen('engine')}>Engine details <ArrowRight size={14} /></button></div>
      </section>
      <section className="panel alerts-panel"><CardTitle title="Maintenance alerts" detail="Threshold-based · review required" action={<button className="round-icon" onClick={() => setScreen('monitoring')} title="Open monitoring"><ArrowRight size={15} /></button>} />
        {recent.length ? <div className="alert-list">{recent.map((alert: any) => <div className="alert-row" key={alert.id}><div className={`alert-symbol ${alert.severity}`}><AlertCircle size={17} /></div><div className="alert-copy"><div><b>{alert.engine_id}</b><Badge tone={alert.severity}>{severityLabel(alert.severity)}</Badge></div><p>Estimated {number(alert.predicted_rul, 1)} cycles remaining · cycle {alert.cycle}</p><span>{new Date(alert.created_at).toLocaleString()}</span></div>{alert.status === 'open' && <button className="ack-button" onClick={() => acknowledge(alert.id)}>Acknowledge</button>}</div>)}</div> : <div className="empty-alerts"><div className="empty-check"><Check size={18} /></div><b>No open alerts</b><span>Fleet remains within configured thresholds.</span></div>}
        <div className="alert-thresholds"><span>Alert thresholds</span><b><i className="dot-amber" /> Watch &lt;60</b><b><i className="dot-orange" /> Warning &lt;30</b><b><i className="dot-red" /> Critical &lt;15</b></div>
      </section>
    </div>
    <div className="content-grid lower-grid">
      <section className="panel fleet-panel"><CardTitle title="Fleet health" detail={`${engines.length} assets · sorted by estimated remaining life`} action={<button className="text-button" onClick={() => setScreen('engine')}>View all <ArrowRight size={14} /></button>} />
        <div className="table-scroll"><table><thead><tr><th>ENGINE</th><th>DATASET</th><th>LAST CYCLE</th><th>EST. REMAINING LIFE</th><th>STATUS</th><th /></tr></thead><tbody>{[...engines].sort((a, b) => a.rul - b.rul).slice(0, 6).map((engine) => <tr key={engine.id} onClick={() => { selectEngine(engine.id); setScreen('engine') }}><td><div className="engine-cell"><span className="engine-mini"><Cpu size={14} /></span><b>{engine.id}</b></div></td><td><span className="subset-text">{engine.subset}</span></td><td>{number(engine.cycle)}</td><td><div className="rul-cell"><b>{number(engine.rul, 1)} <small>cycles</small></b><div className="rul-track"><i className={engine.health} style={{ width: `${Math.min(100, Math.max(8, engine.rul / 1.6))}%` }} /></div></div></td><td><Badge tone={engine.health} dot>{severityLabel(engine.health)}</Badge></td><td><ArrowRight size={14} className="row-arrow" /></td></tr>)}</tbody></table></div>
      </section>
      <section className="panel model-panel"><CardTitle title="Active model" detail="Serving model · versioned artifact" action={<Badge tone="active" dot>ACTIVE</Badge>} />
        <div className="active-model"><div className="model-emblem"><Layers3 size={22} /></div><div><b>{data.model?.algorithm || '—'}</b><span>{data.model?.id}</span></div></div>
        <div className="model-stats"><div><span>Validation MAE</span><b>{number(metrics.mae, 2)}<small> cycles</small></b></div><div><span>Validation RMSE</span><b>{number(metrics.rmse, 2)}<small> cycles</small></b></div><div><span>Validation engines</span><b>{number(metrics.validation_engines)}</b></div></div>
        <div className="model-info"><ShieldCheck size={15} /><span>Validated on held-out engines · cap RUL 125</span></div><button className="secondary-button full-button" onClick={() => setScreen('registry')}>Open model registry <ArrowRight size={14} /></button>
      </section>
    </div>
  </>
}

function EngineScreen({ engine, engines, selectedId, setSelected, startReplay }: any) {
  const [detail, setDetail] = useState<ApiData | null>(null)
  const [sensor, setSensor] = useState('sensor_2')
  useEffect(() => { if (selectedId) void api(`/engines/${selectedId}/history`).then(setDetail).catch(() => setDetail(null)) }, [selectedId])
  return <>
    <PageHeading eyebrow="WORKSPACE · ASSET DETAIL" title="Engine health" detail="Inspect observed sensor history and current model estimates." tag={<Badge tone="demo">RESEARCH DATA</Badge>} action={<button className="primary-button" onClick={startReplay}><Play size={15} fill="currentColor" /> Replay engine</button>} />
    <div className="engine-toolbar panel"><div className="select-label"><span>SELECT ENGINE</span><div className="select-wrap"><Cpu size={16} /><select value={selectedId} onChange={(event) => setSelected(event.target.value)}>{engines.map((item: any) => <option key={item.id} value={item.id}>{item.id} · {item.subset}</option>)}</select><ChevronDown size={15} /></div></div><div className="toolbar-meta"><span>DATA SOURCE</span><b>Historical simulation</b></div><div className="toolbar-meta"><span>OBSERVATIONS</span><b>{number(engine?.observed_cycles)} cycles</b></div><div className="toolbar-meta"><span>LAST CYCLE</span><b>{number(engine?.cycle)}</b></div></div>
    <div className="metric-grid engine-metrics"><MetricCard label="Estimated RUL" value={number(engine?.rul, 1)} suffix="cycles" note="model estimate · not guaranteed" icon={Gauge} tone="blue" /><MetricCard label="Health status" value={severityLabel(engine?.health)} note="based on configured RUL thresholds" icon={Activity} tone={engine?.health === 'critical' ? 'red' : engine?.health === 'warning' ? 'amber' : 'green'} /><MetricCard label="Current cycle" value={number(engine?.cycle)} note="latest observed cycle" icon={Clock3} tone="violet" /><MetricCard label="Model version" value={detail?.engine?.id ? 'Active' : '—'} note="shown in model registry" icon={Layers3} tone="green" /> </div>
    <section className="panel engine-chart-panel"><CardTitle title={`${sensor.replace('_', ' ').replace('sensor', 'Sensor')} history`} detail="Observed telemetry only · model estimates are shown separately." action={<div className="select-wrap compact"><select value={sensor} onChange={(event) => setSensor(event.target.value)}>{Array.from({ length: 21 }, (_, i) => `sensor_${i + 1}`).map((value) => <option key={value}>{value}</option>)}</select><ChevronDown size={14} /></div>} /><div className="chart-legend"><span><i className="legend-blue" /> Observed sensor</span><span><i className="legend-violet" /> Estimated RUL</span></div><div className="engine-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={detail?.series || []} margin={{ top: 12, right: 8, left: -18, bottom: 0 }}><CartesianGrid stroke="#edf0f3" vertical={false} /><XAxis dataKey="cycle" tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} /><YAxis yAxisId="sensor" tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} /><YAxis yAxisId="rul" orientation="right" tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e8ecf0', fontSize: 12 }} /><Line yAxisId="sensor" type="monotone" dataKey={sensor} stroke="#467bdf" strokeWidth={2.2} dot={false} name="Observed sensor" /><Line yAxisId="rul" type="monotone" dataKey="predicted_rul" stroke="#8a72d8" strokeWidth={1.8} strokeDasharray="4 4" dot={false} name="Estimated RUL" /></LineChart></ResponsiveContainer></div></section>
    <div className="content-grid engine-bottom"><section className="panel"><CardTitle title="Current operating conditions" detail="Last observed settings and selected sensors." /><div className="sensor-grid">{[...(detail?.history?.slice(-1) || [])].flatMap((row: any) => ['setting_1', 'setting_2', 'setting_3', 'sensor_2', 'sensor_3', 'sensor_7'].map((key) => <div className="sensor-value" key={key}><span>{key.replace('_', ' ').toUpperCase()}</span><b>{number(row[key], 4)}</b><small>Observed</small></div>))}</div></section><section className="panel notice-panel"><div className="notice-icon"><AlertTriangle size={18} /></div><div><b>Interpret estimates with care</b><p>FailureCast is a research demo using simulated or NASA C-MAPSS data. Predicted RUL is an estimate, not a guaranteed service life or maintenance instruction.</p></div></section></div>
  </>
}

function ReplayScreen({ engines, selectedEngine, setSelected, replay, series, speed, setSpeed, start, action }: any) {
  const latest = replay?.latest
  const step = replay?.position || 0
  const total = replay?.id ? Math.max(1, engines.find((item: any) => item.id === replay.engine_id)?.observed_cycles || 1) : 1
  return <>
    <PageHeading eyebrow="WORKSPACE · HISTORICAL SIMULATION" title="Live replay studio" detail="Replay a historical engine trajectory through the active model and alert thresholds." tag={<Badge tone="demo">SIMULATED TELEMETRY</Badge>} action={replay?.status === 'running' ? <Badge tone="active" dot>REPLAY RUNNING</Badge> : <Badge tone="neutral">{replay?.status || 'READY'}</Badge>} />
    <div className="replay-layout"><section className="panel replay-main"><CardTitle title="Telemetry stream" detail={replay ? `${replay.engine_id} · sequence in cycle order` : 'Choose an engine to begin a replay session.'} action={replay && <Badge tone={replay.status === 'running' ? 'active' : replay.status === 'completed' ? 'normal' : 'neutral'} dot>{replay.status}</Badge>} />
      {!replay ? <div className="replay-empty"><div className="replay-empty-icon"><Waves size={26} /></div><h3>Replay a simulated engine</h3><p>Each observation is sent through the active model. Predictions are stored with the model version and checked against configured alert thresholds.</p><div className="replay-controls"><div className="select-wrap"><Cpu size={15} /><select value={selectedEngine} onChange={(event) => setSelected(event.target.value)}>{engines.map((item: any) => <option key={item.id} value={item.id}>{item.id}</option>)}</select><ChevronDown size={15} /></div><button className="primary-button" onClick={start}><Play size={15} fill="currentColor" /> Start replay</button></div></div> : <>
        <div className="replay-graph"><ResponsiveContainer width="100%" height="100%"><AreaChart data={series} margin={{ top: 10, right: 4, left: -20, bottom: 0 }}><defs><linearGradient id="telemetryFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#30b99b" stopOpacity={0.2} /><stop offset="100%" stopColor="#30b99b" stopOpacity={0} /></linearGradient></defs><CartesianGrid stroke="#edf0f3" vertical={false} /><XAxis dataKey="cycle" tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} /><YAxis tickLine={false} axisLine={false} tick={{ fill: '#98a2b1', fontSize: 11 }} /><Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e8ecf0', fontSize: 12 }} /><Area type="monotone" dataKey="sensor_2" stroke="#30b99b" strokeWidth={2.2} fill="url(#telemetryFill)" dot={false} name="Sensor 2 · observed" /><Line type="monotone" dataKey="rul" stroke="#477de3" strokeWidth={2} dot={false} name="RUL estimate" /></AreaChart></ResponsiveContainer>{!series.length && <div className="chart-overlay"><span className="pulse-dot" /> Waiting for first observation</div>}</div>
        <div className="replay-progress"><div><span>SEQUENCE PROGRESS</span><b>{step} <small>/ {total} observations</small></b></div><div className="progress-track"><i style={{ width: `${Math.min(100, step / total * 100)}%` }} /></div><div className="last-observation"><i /> Cycle {latest?.cycle || '—'} <span>·</span> Sensor data received</div></div>
        <div className="replay-toolbar"><div className="replay-buttons"><button className="round-icon" onClick={() => action('reset')} title="Reset replay"><RotateCcw size={15} /></button>{replay.status === 'running' ? <button className="secondary-button" onClick={() => action('pause')}><Pause size={15} /> Pause</button> : <button className="primary-button" onClick={() => action('resume')}><Play size={15} fill="currentColor" /> Resume</button>}<button className="secondary-button" onClick={() => action('step')} disabled={replay.status !== 'running'}>Step once <ArrowRight size={14} /></button></div><label className="speed-select">SPEED <select value={speed} onChange={(event) => setSpeed(Number(event.target.value))}><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={2}>2×</option><option value={4}>4×</option></select></label></div>
      </>}</section>
      <aside className="panel live-panel"><CardTitle title="Live estimate" detail="Updated with each observed cycle." /><div className={`live-value ${latest?.severity || 'neutral'}`}><b>{number(latest?.rul, 1)}</b><span>cycles</span></div><div className="live-status"><span>Maintenance status</span><Badge tone={latest?.severity || 'neutral'} dot>{severityLabel(latest?.severity)}</Badge></div><div className="live-divider" /><div className="telemetry-list"><div><span><i className="sensor-color green" />Sensor 2</span><b>{number(latest?.sensor_2, 4)}</b></div><div><span><i className="sensor-color blue" />Sensor 3</span><b>{number(latest?.sensor_3, 4)}</b></div><div><span><i className="sensor-color purple" />Sensor 7</span><b>{number(latest?.sensor_7, 4)}</b></div></div><div className="simulation-note"><AlertCircle size={15} /><span>Historical simulation. No live equipment connection or control.</span></div></aside>
    </div>
  </>
}

function DatasetScreen({ datasets, active, files, setFiles, filePickerKey, subset, setSubset, upload, uploading }: any) {
  const [quality, setQuality] = useState<ApiData | null>(null)
  useEffect(() => { if (active?.id) void api(`/datasets/${active.id}/quality`).then(setQuality).catch(() => setQuality(null)) }, [active?.id])
  return <>
    <PageHeading eyebrow="INTELLIGENCE · DATA GOVERNANCE" title="Dataset explorer" detail="Inspect source versions, validate C-MAPSS files and review data quality before training." tag={active?.source === 'Generated local demo data' ? <Badge tone="demo">SIMULATED</Badge> : <Badge tone="active">NASA IMPORT</Badge>} />
    <div className="content-grid dataset-grid"><section className="panel dataset-active"><CardTitle title="Selected dataset" detail="Active data source used for engine views and training jobs." action={<Badge tone="active" dot>ACTIVE</Badge>} /><div className="dataset-summary"><div className="dataset-logo"><Database size={23} /></div><div><b>{active?.name || 'Loading dataset'}</b><span>{active?.source} · {active?.subset}</span></div><div className="dataset-date"><span>VERSION CREATED</span><b>{active?.created_at ? new Date(active.created_at).toLocaleDateString() : 'Built-in demo'}</b></div></div><div className="dataset-facts"><div><span>ENGINES</span><b>{number(quality?.quality?.test?.engines || quality?.quality?.engines || active?.quality?.engines || active?.quality?.train_engines)}</b></div><div><span>OBSERVATIONS</span><b>{number(quality?.quality?.test?.rows || active?.quality?.rows)}</b></div><div><span>SENSORS</span><b>21</b></div><div><span>QUALITY STATUS</span><Badge tone={active?.source === 'Generated local demo data' ? 'demo' : 'normal'} dot>{active?.source === 'Generated local demo data' ? 'Simulated' : 'Passed'}</Badge></div></div>{quality?.checksum && <div className="checksum"><span>SHA-256</span><code>{quality.checksum}</code><button className="copy-button" onClick={() => void navigator.clipboard?.writeText(quality.checksum)} title="Copy checksum"><Check size={13} /></button></div>}</section>
      <section className="panel quality-panel"><CardTitle title="Data quality" detail="Import-time validation results." action={<div className="quality-score"><span>SCHEMA</span><b><i /> VALID</b></div>} /><div className="quality-list"><div><span><Check size={14} /> Required columns and numeric values</span><b>Passed</b></div><div><span><Check size={14} /> Engine IDs and cycle order</span><b>Passed</b></div><div><span><Check size={14} /> Duplicate engine-cycle records</span><b>None</b></div><div><span><Check size={14} /> Missing sensor values</span><b>None</b></div><div><span><Check size={14} /> Test RUL label count matches engines</span><b>{quality?.quality?.rul_labels ? 'Passed' : 'Demo only'}</b></div></div><div className="quality-foot"><ShieldCheck size={15} /> Raw source files are preserved unchanged in the local data directory.</div></section></div>
    <div className="content-grid import-grid"><section className="panel import-panel"><CardTitle title="Import NASA C-MAPSS" detail="Select one official subset and all three matching files." /><div className="import-controls"><label className="field-group"><span>DATASET SUBSET</span><div className="select-wrap"><select value={subset} onChange={(event) => setSubset(event.target.value)}>{['FD001', 'FD002', 'FD003', 'FD004'].map((item) => <option key={item}>{item}</option>)}</select><ChevronDown size={14} /></div></label><div className="accepted-files"><span>REQUIRED FILE NAMES</span><code>train_{subset}.txt</code><code>test_{subset}.txt</code><code>RUL_{subset}.txt</code></div></div><label className="dropzone"><UploadCloud size={22} /><b>{files?.length ? `${files.length} files selected` : 'Drop files here or browse'}</b><span>Official whitespace-delimited files · up to 20 MB each</span><input key={filePickerKey} type="file" multiple accept=".txt,text/plain" onChange={(event) => setFiles(event.target.files)} /></label><div className="import-footer"><span>Files are validated before they are stored. Duplicate imports reuse their existing version.</span><button className="primary-button" onClick={upload} disabled={uploading}>{uploading ? <><span className="button-spinner" /> Importing</> : <><UploadCloud size={15} /> Validate & import</>}</button></div></section>
      <section className="panel version-panel"><CardTitle title="Dataset versions" detail={`${datasets.length} registered source${datasets.length === 1 ? '' : 's'}.`} /><div className="version-list">{datasets.map((dataset: any) => <div className="version-row" key={dataset.id}><span className="version-icon"><Database size={15} /></span><div className="version-copy"><b>{dataset.source === 'Generated local demo data' ? 'Simulated sample · FD001' : `NASA C-MAPSS · ${dataset.subset}`}</b><span>{dataset.id}</span></div>{dataset.active && <Badge tone="active" dot>ACTIVE</Badge>}</div>)}</div><p className="version-note">NASA C-MAPSS is simulated turbofan data. It does not represent real aircraft maintenance measurements.</p></section></div>
  </>
}

function ExperimentsScreen({ models, jobs, algorithm, setAlgorithm, train, busy }: any) {
  return <>
    <PageHeading eyebrow="INTELLIGENCE · MODEL DEVELOPMENT" title="Experiments" detail="Train reproducible candidates, compare engine-held-out results and keep the active model in service." tag={<Badge tone="neutral">SEED 41 · FEATURE PIPELINE V1</Badge>} action={<button className="primary-button" onClick={train} disabled={busy}><Zap size={15} /> Start training</button>} />
    <section className="panel train-panel"><div className="train-intro"><div className="train-icon"><Cpu size={19} /></div><div><b>Train a candidate model</b><span>Training runs asynchronously on the selected dataset and validates by engine ID.</span></div></div><div className="train-form"><label className="field-group"><span>ALGORITHM</span><div className="select-wrap"><select value={algorithm} onChange={(event) => setAlgorithm(event.target.value)}><option>MeanBaseline</option><option>HistGradientBoostingRegressor</option><option>RandomForestRegressor</option><option>LSTM</option></select><ChevronDown size={14} /></div></label><div className="train-facts"><span><ShieldCheck size={14} /> 80/20 engine-level holdout</span><span><Activity size={14} /> Capped RUL target: 125</span></div><button className="primary-button" onClick={train} disabled={busy}><Zap size={15} /> Queue training job</button></div><p className="train-note">The official test set is kept out of model selection. LSTM training requires the optional PyTorch dependency.</p></section>
    <section className="panel table-panel"><CardTitle title="Model comparison" detail="Validation metrics are reported on held-out engines and stay linked to their dataset version." action={<span className="table-meta">{models.length} registered versions</span>} /><div className="table-scroll"><table><thead><tr><th>MODEL</th><th>ALGORITHM</th><th>VALIDATION MAE</th><th>RMSE</th><th>BIAS</th><th>ENGINES</th><th>STATUS</th></tr></thead><tbody>{models.map((model: any) => <tr key={model.id}><td><div className="model-name"><span className="model-mini"><Layers3 size={14} /></span><b>{model.id}</b></div></td><td>{model.algorithm}</td><td>{number(model.metrics?.mae, 2)} <small>cycles</small></td><td>{number(model.metrics?.rmse, 2)}</td><td>{number(model.metrics?.bias, 2)}</td><td>{number(model.metrics?.validation_engines)}</td><td><Badge tone={model.status === 'active' ? 'active' : model.status}>{model.status}</Badge></td></tr>)}</tbody></table></div></section>
    <section className="panel table-panel jobs-panel"><CardTitle title="Training jobs" detail="Recent local runs and candidate registration." /><div className="table-scroll"><table><thead><tr><th>JOB</th><th>ALGORITHM</th><th>CREATED</th><th>STATUS</th><th>RESULT</th></tr></thead><tbody>{jobs.length ? jobs.map((job: any) => <tr key={job.id}><td><code>{job.id}</code></td><td>{job.algorithm}</td><td>{new Date(job.created_at).toLocaleString()}</td><td><Badge tone={job.status === 'completed' ? 'normal' : job.status === 'failed' ? 'critical' : 'demo'} dot>{job.status}</Badge></td><td>{job.result?.model_id || job.error || '—'}</td></tr>) : <tr><td colSpan={5} className="empty-cell">No training jobs yet. Queue a run to register the first candidate.</td></tr>}</tbody></table></div></section>
  </>
}

function ExplainScreen({ engine, engines, selectedId, setSelected, explanation }: any) {
  const max = Math.max(0.00001, ...(explanation?.items || []).map((item: any) => item.sensitivity))
  return <>
    <PageHeading eyebrow="INTELLIGENCE · MODEL BEHAVIOR" title="Explainability explorer" detail="Review which current sensor values have the strongest local effect on this model’s estimate." tag={<Badge tone="neutral">PERTURBATION SENSITIVITY</Badge>} action={<div className="select-wrap"><Cpu size={15} /><select value={selectedId} onChange={(event) => setSelected(event.target.value)}>{engines.map((item: any) => <option key={item.id} value={item.id}>{item.id}</option>)}</select><ChevronDown size={14} /></div>} />
    <div className="explain-grid"><section className="panel sensitivity-panel"><CardTitle title="Local sensor sensitivity" detail={engine?.id ? `${engine.id} · current observation` : 'Select an engine to calculate local sensitivity.'} action={<span className="subtle-select">ACTIVE MODEL</span>} />{explanation?.items?.length ? <div className="sensitivity-list">{explanation.items.map((item: any, index: number) => <div className="sensitivity-row" key={item.sensor}><div className="sensitivity-top"><span><i className={`rank-dot rank-${index + 1}`} />{item.sensor.replace('_', ' ')}</span><b>{number(item.sensitivity, 3)} <small>cycles</small></b></div><div className="sensitivity-track"><i style={{ width: `${Math.max(2, item.sensitivity / max * 100)}%` }} /></div></div>)}</div> : <div className="empty-state">Sensitivity report is being calculated…</div>}<div className="model-info sensitivity-info"><Sparkles size={15} /><span>{explanation?.type || 'Local feature sensitivity'} · based on sensor perturbation</span></div></section>
      <aside className="panel explanation-note"><div className="explain-art"><div className="explain-orbit orbit-a" /><div className="explain-orbit orbit-b" /><div className="explain-core"><Sparkles size={25} /></div></div><span className="eyebrow">HOW TO READ THIS</span><h3>Signal sensitivity, not certainty.</h3><p>Each value shows how much the current estimate changes when one sensor group is replaced with its training median. This helps investigate model behavior; it does not prove causality.</p><div className="note-separator" /><div className="small-note"><ShieldCheck size={15} /><span>No confidence percentage is shown because this model has no calibrated uncertainty interval.</span></div></aside></div>
  </>
}

function MonitoringScreen({ drift, model, refresh, setScreen, announce }: any) {
  const [checking, setChecking] = useState(false)
  const [shiftEnabled, setShiftEnabled] = useState(false)
  useEffect(() => setShiftEnabled(Boolean(drift?.simulation)), [drift?.simulation?.sensor, drift?.simulation?.sigma])
  const run = async () => { setChecking(true); await refresh(); setChecking(false) }
  const simulate = async () => {
    setChecking(true)
    try {
      const result = await api('/monitoring/drift/simulate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ enabled: !shiftEnabled, sensor: 'sensor_2', sigma: 4 }) })
      setShiftEnabled(Boolean(result.simulation)); await refresh()
    } catch (error) { announce((error as Error).message) }
    finally { setChecking(false) }
  }
  return <>
    <PageHeading eyebrow="CONTROL ROOM · DATA QUALITY" title="Model monitoring" detail="Review incoming sensor distributions and operational signals before starting a candidate run." tag={<Badge tone={drift?.status === 'investigate' ? 'warning' : 'normal'} dot>{drift?.status === 'investigate' ? 'REVIEW SIGNAL' : 'DISTRIBUTION STABLE'}</Badge>} action={<><button className="secondary-button" onClick={simulate} disabled={checking}><Waves size={15} /> {shiftEnabled ? 'Remove simulated shift' : 'Simulate 4σ shift'}</button><button className="secondary-button" onClick={run} disabled={checking}><RotateCcw size={15} /> Refresh</button></>} />
    <div className="monitor-summary-grid"><div className="panel monitor-score"><span className="eyebrow">FEATURE SHIFT SCORE</span><div className="drift-score">{drift ? number(drift.score * 100, 0) : '—'}<small>%</small></div><div className="drift-meter"><i style={{ width: `${Math.min(100, (drift?.score || 0) * 100)}%` }} /></div><div className="monitor-status-line"><span><i className={drift?.status === 'investigate' ? 'amber-dot' : 'green-dot'} />{drift?.status === 'investigate' ? 'Investigate shifted features' : 'Within review range'}</span><span>Last 12 observations</span></div></div><div className="panel monitor-summary"><div className="monitor-summary-icon blue"><Activity size={19} /></div><span>Monitored features</span><b>21 <small>sensors</small></b><p>Compared with the selected training baseline.</p></div><div className="panel monitor-summary"><div className="monitor-summary-icon green"><Zap size={18} /></div><span>Active model</span><b>{model || '—'}</b><p>Drift is a review signal; it never promotes a model.</p></div></div>
    <section className="panel table-panel drift-panel"><CardTitle title="Feature distribution shift" detail={`${drift?.window || '—'} · normalized mean shift in standard deviations`} action={<span className="table-meta">Baseline · {drift?.baseline || 'training data'}</span>} /><div className="drift-list">{(drift?.items || []).map((item: any) => <div className="drift-row" key={item.sensor}><div className="drift-name"><span className={`sensor-bullet ${item.status}`} />{item.sensor.replace('_', ' ')}</div><div className="drift-bar"><i className={item.status} style={{ width: `${Math.min(100, item.shift_sigma / 5 * 100)}%` }} /></div><b>{number(item.shift_sigma, 2)}σ</b><Badge tone={item.status === 'shift' ? 'warning' : 'normal'}>{item.status}</Badge></div>)}</div><div className="drift-disclaimer"><AlertCircle size={15} />{drift?.note || 'Distribution changes require investigation. They are not a failure prediction.'}</div></section>
    <div className="monitor-note"><div className="monitor-note-icon"><ShieldCheck size={18} /></div><div><b>Retraining stays controlled</b><p>Drift reports do not trigger training or model activation. Create a candidate in Experiments, compare validation results, then approve any promotion from the registry.</p></div><button className="text-button" onClick={() => setScreen('experiments')}>Open experiments <ArrowRight size={14} /></button></div>
  </>
}

function RegistryScreen({ models, refresh, announce }: any) {
  const [busyId, setBusyId] = useState('')
  const [confirmModel, setConfirmModel] = useState<ApiData | null>(null)
  const [audit, setAudit] = useState<ApiData[]>([])
  useEffect(() => { void api('/audit').then((result) => setAudit(result.items)).catch(() => setAudit([])) }, [models.length])
  const promote = async () => {
    if (!confirmModel) return
    setBusyId(confirmModel.id)
    try {
      await api(`/models/${confirmModel.id}/promote`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ approved: true }) })
      announce(`Model ${confirmModel.id} is active.`); setConfirmModel(null); await refresh(); setAudit((await api('/audit')).items)
    } catch (error) { announce((error as Error).message) }
    finally { setBusyId('') }
  }
  const rollback = async () => {
    setBusyId('rollback')
    try { const result = await api('/models/rollback', { method: 'POST' }); announce(`Restored ${result.id} as the active model.`); await refresh(); setAudit((await api('/audit')).items) }
    catch (error) { announce((error as Error).message) }
    finally { setBusyId('') }
  }
  const rollbackAvailable = models.some((model: any) => model.status === 'approved')
  const evaluate = async (model: any) => {
    setBusyId(model.id)
    try {
      const report = await api(`/models/${model.id}/evaluate`, { method: 'POST' })
      const blob = new Blob([JSON.stringify(report, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = `failurecast-evaluation-${model.id}.json`; link.click(); URL.revokeObjectURL(url)
      announce(`Final-cycle evaluation: MAE ${number(report.mae, 2)}, RMSE ${number(report.rmse, 2)} cycles across ${report.test_engines} engines.`)
      setAudit((await api('/audit')).items)
    } catch (error) { announce((error as Error).message) }
    finally { setBusyId('') }
  }
  return <>
    <PageHeading eyebrow="CONTROL ROOM · MODEL LIFECYCLE" title="Model registry" detail="Review validation evidence, explicitly promote a candidate and restore a previous approved version." tag={<Badge tone="active" dot>CONTROLLED DEPLOYMENT</Badge>} action={<button className="secondary-button" disabled={!rollbackAvailable || busyId === 'rollback'} onClick={rollback}><RotateCcw size={15} /> {busyId === 'rollback' ? 'Restoring…' : 'Roll back'}</button>} />
    <section className="panel registry-panel"><CardTitle title="Registered versions" detail="Only locally created, validated artifacts are loaded by the inference service." action={<span className="table-meta">{models.length} versions</span>} /><div className="table-scroll"><table><thead><tr><th>VERSION</th><th>MODEL</th><th>DATASET</th><th>VALIDATION MAE</th><th>CREATED</th><th>STATE</th><th>ACTION</th></tr></thead><tbody>{models.map((model: any) => <tr key={model.id}><td><div className="model-name"><span className="model-mini"><Layers3 size={14} /></span><b>{model.id}</b></div></td><td>{model.algorithm}</td><td>{model.dataset_id || 'Demo · FD001'}</td><td>{number(model.metrics?.mae, 2)} <small>cycles</small></td><td>{new Date(model.created_at).toLocaleDateString()}</td><td><Badge tone={model.status === 'active' ? 'active' : model.status}>{model.status}</Badge></td><td>{model.status === 'candidate' ? <button className="table-action" onClick={() => setConfirmModel(model)}>Review & promote <ArrowRight size={13} /></button> : model.status === 'active' ? <button className="table-action" onClick={() => evaluate(model)} disabled={busyId === model.id}>{busyId === model.id ? 'Evaluating…' : 'Evaluate test set'} <ArrowRight size={13} /></button> : <span className="muted-action">Rollback ready</span>}</td></tr>)}</tbody></table></div></section>
    <section className="panel audit-panel"><CardTitle title="Deployment history" detail="Model lifecycle actions recorded locally." /><div className="audit-list">{audit.length ? audit.map((event: any) => <div className="audit-row" key={event.id}><span className="audit-icon"><GitBranch size={15} /></span><div><b>{event.action === 'promote' ? 'Model promoted' : event.action === 'rollback' ? 'Model rollback' : event.action === 'official_test_evaluation' ? 'Final test evaluation' : 'Alert acknowledged'}</b><span>{event.model_id || JSON.parse(event.details).alert_id} · {new Date(event.created_at).toLocaleString()}</span></div><Badge tone="normal">RECORDED</Badge></div>) : <div className="empty-cell">No deployment events recorded yet.</div>}</div></section>
    {confirmModel && <div className="modal-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setConfirmModel(null) }}><section className="confirm-modal" role="dialog" aria-modal="true" aria-labelledby="promote-title"><button className="modal-close" onClick={() => setConfirmModel(null)} aria-label="Close"><X size={17} /></button><div className="modal-symbol"><ShieldCheck size={20} /></div><span className="eyebrow">CANDIDATE APPROVAL</span><h2 id="promote-title">Activate this model version?</h2><p><b>{confirmModel.id}</b> · {confirmModel.algorithm}. This will switch new predictions to the candidate and preserve the current version for rollback.</p><div className="modal-metrics"><div><span>Validation MAE</span><b>{number(confirmModel.metrics?.mae, 2)} cycles</b></div><div><span>Holdout engines</span><b>{number(confirmModel.metrics?.validation_engines)}</b></div></div><div className="modal-actions"><button className="secondary-button" onClick={() => setConfirmModel(null)}>Cancel</button><button className="primary-button" onClick={promote} disabled={!!busyId}>{busyId ? 'Activating…' : <><Check size={15} /> Approve & activate</>}</button></div></section></div>}
  </>
}

export default App

```

## frontend/src/main.tsx — entry and global stylesheet mount

```tsx
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './styles.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)

```
