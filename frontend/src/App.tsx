import { useCallback, useEffect, useMemo, useState } from 'react'
import type { FormEvent, ReactNode } from 'react'
import {
  Activity, AlertCircle, AlertTriangle, ArrowDownRight, ArrowRight, Boxes, Check,
  ChevronDown, CircleHelp, Clock3, Cpu, Database, Download, Gauge, GitBranch,
  Layers3, LineChart as LineIcon, LockKeyhole, LogOut, Menu, Pause, Play, RotateCcw, Settings2,
  ShieldCheck, Sparkles, UploadCloud, Waves, X, Zap,
} from 'lucide-react'
import {
  Area, AreaChart, CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
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

function WelcomePage({ onStart }: { onStart: () => void }) {
  return <main className="welcome-page">
    <header className="welcome-nav">
      <div className="welcome-brand"><span className="welcome-brand-mark"><Activity size={20} strokeWidth={2.4} /></span><span><b>failurecast</b><small>RELIABILITY INTELLIGENCE</small></span></div>
      <span className="welcome-demo-label"><i /> RESEARCH DEMO · SIMULATED DATA</span>
    </header>

    <section className="welcome-hero">
      <div className="welcome-copy">
        <span className="welcome-kicker"><i /> PREDICTIVE MAINTENANCE · END-TO-END MLOPS</span>
        <h1>See what the engine data is telling you.</h1>
        <p>FailureCast is a local-first predictive maintenance and MLOps platform for simulated turbofan engines. It takes sensor data through validation, remaining-life forecasting, controlled model releases, and monitoring.</p>
        <button className="welcome-cta" onClick={onStart}>Get started <ArrowRight size={17} /></button>
        <div className="welcome-safety"><ShieldCheck size={16} /><span>Research estimates for investigation · no equipment control</span></div>
      </div>

      <div className="welcome-visual" role="img" aria-label="Illustration of sensor history becoming a remaining useful life forecast and a maintenance review">
        <div className="welcome-visual-glow" />
        <div className="welcome-visual-head"><span><i /> ILLUSTRATIVE ENGINE SIGNAL</span><b>FROM SENSOR TO REVIEW</b></div>
        <div className="welcome-chart-title"><div><small>ENGINE TRAJECTORY</small><strong>Remaining useful life</strong></div><span>SIMULATED</span></div>
        <div className="welcome-chart-wrap">
          <div className="welcome-chart-axis"><span>MORE</span><span>RUL</span><span>LESS</span></div>
          <svg className="welcome-chart-svg" viewBox="0 0 560 260" preserveAspectRatio="none" aria-hidden="true">
            <defs><linearGradient id="welcomeArea" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#72d7ba" stopOpacity=".22" /><stop offset="100%" stopColor="#72d7ba" stopOpacity="0" /></linearGradient></defs>
            <path className="welcome-grid-line" d="M0 35H560M0 96H560M0 157H560M0 218H560" />
            <path d="M0 24 C35 26 48 34 72 40 S118 49 140 56 S180 62 205 80 S247 87 270 103 S310 107 330 131 S372 140 393 155 S433 162 452 185 S494 191 513 207 S544 215 560 229 L560 260 L0 260Z" fill="url(#welcomeArea)" />
            <path className="welcome-estimate-line" d="M0 24 C35 26 48 34 72 40 S118 49 140 56 S180 62 205 80 S247 87 270 103 S310 107 330 131 S372 140 393 155 S433 162 452 185 S494 191 513 207 S544 215 560 229" fill="none" stroke="#72d7ba" strokeWidth="3" vectorEffect="non-scaling-stroke" />
            <path className="welcome-reference-line" d="M0 36 C40 39 54 42 77 48 S120 54 145 66 S184 73 208 86 S249 93 272 111 S311 116 334 137 S375 146 396 164 S435 171 455 190 S496 199 517 213 S546 220 560 235" fill="none" stroke="#90a7c2" strokeOpacity=".75" strokeWidth="2" strokeDasharray="6 7" vectorEffect="non-scaling-stroke" />
            <circle className="welcome-current-point" cx="560" cy="229" r="5" fill="#72d7ba" stroke="#122332" strokeWidth="3" vectorEffect="non-scaling-stroke" />
          </svg>
          <div className="welcome-chart-x"><span>EARLIER CYCLES</span><span>RECENT OBSERVATIONS</span></div>
        </div>
        <div className="welcome-flow"><span><i>01</i> Sensor history</span><ArrowRight size={14} /><span><i>02</i> RUL estimate</span><ArrowRight size={14} /><span><i>03</i> Review priority</span></div>
        <p className="welcome-visual-caption">Illustrative trajectory · actual estimates depend on the selected dataset and model</p>
      </div>
    </section>

    <section className="welcome-steps" aria-label="What FailureCast helps you do">
      <div className="welcome-step"><span>01 / INGEST & VALIDATE</span><b>Start with trustworthy data</b><p>Import engine histories, check data quality, and preserve dataset provenance.</p></div>
      <div className="welcome-step"><span>02 / FORECAST & REVIEW</span><b>Put risk in context</b><p>Estimate remaining life, rank assets, inspect sensor history, and replay a trajectory.</p></div>
      <div className="welcome-step"><span>03 / EVALUATE & GOVERN</span><b>Keep model changes controlled</b><p>Compare held-out results, review drift, and approve or roll back model versions.</p></div>
    </section>

    <footer className="welcome-footer"><span>FailureCast · Predictive maintenance research platform</span><span>Built-in sample data is simulated · estimates are not maintenance instructions</span></footer>
  </main>
}

function App() {
  const [hasStarted, setHasStarted] = useState(() => sessionStorage.getItem('failurecast:started') === 'true')
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
  const startReplay = async (engineId = selectedEngine) => {
    if (!engineId) return
    try {
      const session = await api('/replay/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ engine_id: engineId, speed: replaySpeed }) })
      setSelectedEngine(engineId); setReplay(session); setReplaySeries([]); setNotice('Historical sensor replay started.')
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

  if (!hasStarted) return <WelcomePage onStart={() => { sessionStorage.setItem('failurecast:started', 'true'); setHasStarted(true) }} />
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
  const thresholds = data.thresholds || { critical: 15, warning: 30, watch: 60 }
  const riskAssets = engines
    .filter((engine: ApiData) => engine.rul != null && Number.isFinite(Number(engine.rul)))
    .sort((a: ApiData, b: ApiData) => Number(a.rul) - Number(b.rul))
  const priorityEngine = riskAssets[0]
  const statusCounts = engines.reduce((counts: Record<string, number>, engine: ApiData) => {
    if (Object.prototype.hasOwnProperty.call(counts, engine.health)) counts[engine.health] += 1
    return counts
  }, { normal: 0, watch: 0, warning: 0, critical: 0 })
  const recent = alerts.filter((alert: ApiData) => alert.status === 'open').slice(0, 3)
  const [focusDetail, setFocusDetail] = useState<ApiData | null>(null)
  const [focusExplanation, setFocusExplanation] = useState<ApiData | null>(null)
  const [focusLoading, setFocusLoading] = useState(false)

  useEffect(() => {
    if (!priorityEngine?.id) {
      setFocusDetail(null); setFocusExplanation(null); setFocusLoading(false)
      return
    }
    let current = true
    setFocusDetail(null); setFocusExplanation(null); setFocusLoading(true)
    Promise.all([
      api(`/engines/${encodeURIComponent(priorityEngine.id)}/history`).catch(() => null),
      api(`/explain/${encodeURIComponent(priorityEngine.id)}`).catch(() => null),
    ]).then(([detail, explanation]) => {
      if (!current) return
      setFocusDetail(detail); setFocusExplanation(explanation)
    }).finally(() => { if (current) setFocusLoading(false) })
    return () => { current = false }
  }, [priorityEngine?.id, priorityEngine?.cycle, priorityEngine?.rul, data.model?.id])

  const exportReport = () => {
    const file = new Blob([JSON.stringify({ generated_at: new Date().toISOString(), dataset: data.dataset, model: data.model, summary: data.summary, alerts }, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(file); const link = document.createElement('a'); link.href = url; link.download = 'failurecast-evaluation-summary.json'; link.click(); URL.revokeObjectURL(url)
  }
  const inspectPriority = () => {
    if (!priorityEngine?.id) return
    selectEngine(priorityEngine.id); setScreen('engine')
  }
  const startPriorityReplay = () => { if (priorityEngine?.id) void startReplay(priorityEngine.id) }
  const sensitivity = focusExplanation?.items?.slice(0, 3) || []
  const maxSensitivity = Math.max(0, ...sensitivity.map((item: ApiData) => Number(item.sensitivity) || 0))
  const sourceNote = data.dataset?.quality?.data_quality || 'Historical dataset; no live equipment connection.'

  return <div className="overview-page">
    <header className="overview-heading">
      <div>
        <div className="overview-eyebrow"><span className="eyebrow">FLEET OPERATIONS</span><Badge tone="demo" dot>{data.dataset?.subset || 'DATASET'} · SIMULATED</Badge></div>
        <h1>See the signal. Plan the review.</h1>
        <p>Cycle-by-cycle engine estimates, review thresholds, and the evidence behind each signal.</p>
      </div>
      <div className="heading-action">
        <button className="secondary-button" onClick={exportReport}><Download size={15} /> Export report</button>
        <button className="primary-button" onClick={startPriorityReplay} disabled={!priorityEngine}><Play size={15} fill="currentColor" /> Start historical replay</button>
      </div>
    </header>

    <nav className="demo-flow" aria-label="Demo walkthrough">
      <span className="demo-flow-label">DEMO WALKTHROUGH</span>
      <span className="demo-step active" aria-current="step"><i>01</i><b>Assess fleet risk</b></span>
      <span className="demo-flow-line" />
      <button className="demo-step" onClick={inspectPriority} disabled={!priorityEngine}><i>02</i><b>Inspect trajectory</b><ArrowRight size={14} /></button>
      <span className="demo-flow-line" />
      <button className="demo-step" onClick={startPriorityReplay} disabled={!priorityEngine}><i>03</i><b>Replay estimate</b><ArrowRight size={14} /></button>
    </nav>

    <section className="overview-kpis" aria-label="Fleet summary">
      <div className="overview-kpi"><span className="kpi-icon blue"><Cpu size={17} /></span><div><small>FLEET ASSETS</small><strong>{number(data.summary?.engines ?? engines.length)}</strong><span>in {data.dataset?.subset || 'selected dataset'}</span></div></div>
      <div className="overview-kpi"><span className="kpi-icon amber"><AlertTriangle size={17} /></span><div><small>NEED REVIEW</small><strong>{number(statusCounts.critical + statusCounts.warning + statusCounts.watch)}</strong><span>{statusCounts.warning} warning · {statusCounts.watch} watch</span></div></div>
      <div className="overview-kpi"><span className="kpi-icon teal"><Gauge size={17} /></span><div><small>MEDIAN ESTIMATED RUL</small><strong>{number(data.summary?.median_rul, 1)} <em>cycles</em></strong><span>model estimate · not a guarantee</span></div></div>
      <div className="overview-kpi"><span className="kpi-icon violet"><LineIcon size={17} /></span><div><small>VALIDATION MAE</small><strong>{number(metrics.mae, 2)} <em>cycles</em></strong><span>engine-level holdout · {number(metrics.validation_engines)} engines</span></div></div>
    </section>

    <section className="risk-hero" aria-label="Highest-risk engine and remaining-life trajectory">
      <article className="priority-card panel">
        <div className="priority-card-head"><div><span className="section-kicker">PRIORITY ASSET</span><h2>{priorityEngine?.id || 'No engine selected'}</h2></div>{priorityEngine && <Badge tone={priorityEngine.health} dot>{severityLabel(priorityEngine.health)}</Badge>}</div>
        <p className="priority-summary">Lowest current model-estimated remaining life in this fleet.</p>
        <div className="priority-rul"><strong>{priorityEngine ? number(priorityEngine.rul, 1) : '—'}</strong><span>cycles estimated</span></div>
        <div className="priority-cycle"><Clock3 size={15} /><span>Latest available observation</span><b>Cycle {number(priorityEngine?.cycle)}</b></div>
        <div className="rul-scale-heading"><span>Review thresholds</span><span>Model cap · 125 cycles</span></div>
        <div className="rul-scale" role="img" aria-label={`Estimated remaining life ${number(priorityEngine?.rul, 1)} cycles; warning below ${thresholds.warning}, critical below ${thresholds.critical}`}>
          <div className="rul-scale-band" />
          {priorityEngine && <i className="rul-scale-marker" style={{ left: `${Math.min(100, Math.max(0, Number(priorityEngine.rul) / 125 * 100))}%` }} />}
        </div>
        <div className="rul-scale-values"><span>0</span><span>{number(thresholds.critical)}</span><span>{number(thresholds.warning)}</span><span>{number(thresholds.watch)}</span><span>125</span></div>
        <div className="threshold-legend"><span><i className="critical" />Critical &lt;{number(thresholds.critical)}</span><span><i className="warning" />Warning &lt;{number(thresholds.warning)}</span><span><i className="watch" />Watch &lt;{number(thresholds.watch)}</span></div>
        <div className="priority-actions"><button className="primary-button" onClick={inspectPriority} disabled={!priorityEngine}><Activity size={15} /> Inspect engine</button><button className="secondary-button" onClick={startPriorityReplay} disabled={!priorityEngine}><Play size={14} fill="currentColor" /> Replay history</button></div>
        <p className="estimate-disclaimer"><ShieldCheck size={14} /> Historical simulation. RUL is a model estimate, not guaranteed service life or maintenance advice.</p>
      </article>

      <section className="trajectory-card panel">
        <div className="trajectory-head"><div><span className="section-kicker">ENGINE TRAJECTORY</span><h2>Remaining useful life</h2><p>{priorityEngine?.id || 'Selected engine'} · cycle-by-cycle reference label vs model estimate</p></div><Badge tone="demo">HISTORICAL</Badge></div>
        <div className="trajectory-legend"><span><i className="trajectory-model" />Model estimate</span><span><i className="trajectory-target" />Reference RUL</span><span className="trajectory-current">CURRENT · CYCLE {number(priorityEngine?.cycle)}</span></div>
        <div className="overview-trajectory-chart">
          {focusDetail?.series?.length ? <ResponsiveContainer width="100%" height="100%"><AreaChart data={focusDetail.series} margin={{ top: 12, right: 12, left: -18, bottom: 0 }}><defs><linearGradient id="priorityRulFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#497fe0" stopOpacity={0.18} /><stop offset="95%" stopColor="#497fe0" stopOpacity={0.01} /></linearGradient></defs><CartesianGrid stroke="#edf1f4" vertical={false} /><XAxis dataKey="cycle" tickLine={false} axisLine={false} tick={{ fill: '#8e99a7', fontSize: 11 }} tickMargin={10} /><YAxis domain={[0, 125]} ticks={[0, 30, 60, 90, 120]} tickLine={false} axisLine={false} tick={{ fill: '#8e99a7', fontSize: 11 }} tickMargin={8} /><Tooltip contentStyle={{ borderRadius: 10, border: '1px solid #e5eaf0', boxShadow: '0 8px 24px #15233712', fontSize: 12 }} /><ReferenceLine y={thresholds.warning} stroke="#d49a49" strokeDasharray="4 5" /><ReferenceLine y={thresholds.critical} stroke="#ca7470" strokeDasharray="4 5" /><Area type="monotone" dataKey="predicted_rul" stroke="#477de3" strokeWidth={2.6} fill="url(#priorityRulFill)" dot={false} activeDot={{ r: 4, strokeWidth: 2 }} name="Model estimate" /><Line type="monotone" dataKey="actual_rul" stroke="#8693a3" strokeWidth={1.8} strokeDasharray="5 5" dot={false} name="Simulation target" connectNulls={false} /></AreaChart></ResponsiveContainer> : <div className="overview-chart-empty" role="status">{focusLoading ? 'Loading engine history…' : 'Engine history is unavailable for this asset.'}</div>}
        </div>
        <div className="trajectory-foot"><span><i />{focusDetail?.series?.length ? `${number(focusDetail.series.length)} historical observations · source: ${data.dataset?.name || 'selected dataset'}` : sourceNote}</span><button className="text-button" onClick={inspectPriority} disabled={!priorityEngine}>Open engine detail <ArrowRight size={14} /></button></div>
      </section>
    </section>

    <section className="overview-detail-grid">
      <section className="panel risk-ranking-panel">
        <div className="overview-panel-head"><div><span className="section-kicker">FLEET CONDITION</span><h2>Risk ranking</h2><p>Sorted by lowest model-estimated remaining life.</p></div><button className="text-button" onClick={() => setScreen('engine')}>All engines <ArrowRight size={14} /></button></div>
        <div className="risk-ranking-list">{riskAssets.slice(0, 5).map((engine: ApiData, index: number) => <button className={`risk-engine-row ${index === 0 ? 'selected' : ''}`} key={engine.id} onClick={() => { selectEngine(engine.id); setScreen('engine') }}><span className="risk-rank">{String(index + 1).padStart(2, '0')}</span><span className="risk-engine-name"><b>{engine.id}</b><small>{engine.subset} · cycle {number(engine.cycle)}</small></span><span className="risk-engine-rul"><b>{number(engine.rul, 1)}</b><small>cycles</small></span><Badge tone={engine.health} dot>{severityLabel(engine.health)}</Badge><ArrowRight size={15} className="risk-engine-arrow" /></button>)}</div>
        {!riskAssets.length && <div className="overview-empty">Engine estimates are not available.</div>}
        <div className="risk-counts"><span><i className="normal" />{statusCounts.normal} Normal</span><span><i className="watch" />{statusCounts.watch} Watch</span><span><i className="warning" />{statusCounts.warning} Warning</span><span><i className="critical" />{statusCounts.critical} Critical</span></div>
      </section>

      <div className="overview-evidence-stack">
        <section className="panel model-evidence-panel">
          <div className="overview-panel-head"><div><span className="section-kicker">MODEL EVIDENCE</span><h2>Active model validation</h2></div><Badge tone="active" dot>ACTIVE</Badge></div>
          <div className="evidence-model-name"><span className="evidence-model-icon"><Layers3 size={18} /></span><div><b>{data.model?.algorithm || 'No active model'}</b><small>{data.model?.id || '—'}</small></div></div>
          <div className="evidence-metrics"><div><span>MAE</span><b>{number(metrics.mae, 2)} <small>cycles</small></b></div><div><span>RMSE</span><b>{number(metrics.rmse, 2)} <small>cycles</small></b></div><div><span>Validation</span><b>{number(metrics.validation_engines)} <small>engines</small></b></div></div>
          <div className="evidence-note"><ShieldCheck size={15} /><span>Engine-level holdout · {number(metrics.training_engines)} training engines · model selection kept separate from final test evaluation.</span></div>
          <button className="secondary-button evidence-link" onClick={() => setScreen('registry')}>Review model registry <ArrowRight size={14} /></button>
        </section>

        <section className="panel sensitivity-evidence-panel">
          <div className="overview-panel-head"><div><span className="section-kicker">LOCAL EXPLAINABILITY</span><h2>Most sensitive inputs</h2></div><button className="text-button" onClick={() => { if (priorityEngine) selectEngine(priorityEngine.id); setScreen('explain') }}>Explore <ArrowRight size={13} /></button></div>
          {sensitivity.length ? <div className="sensitivity-evidence-list">{sensitivity.map((item: ApiData) => <div className="sensitivity-evidence-row" key={item.sensor}><span>{item.sensor.replace('_', ' ')}</span><div><i style={{ width: `${Math.max(2, (Number(item.sensitivity) || 0) / Math.max(maxSensitivity, 0.00001) * 100)}%` }} /></div><b>{number(item.sensitivity, 2)} <small>cycles</small></b></div>)}</div> : <p className="sensitivity-empty">{focusLoading ? 'Calculating local sensitivity…' : 'Sensitivity data is not available for this model.'}</p>}
          <p className="sensitivity-disclaimer">Perturbation sensitivity describes local model response; it is not a causal fault diagnosis.</p>
        </section>

        <section className="panel overview-alerts-panel">
          <div className="overview-panel-head"><div><span className="section-kicker">REVIEW QUEUE</span><h2>Threshold alerts</h2></div><button className="text-button" onClick={() => setScreen('monitoring')}>Monitoring <ArrowRight size={13} /></button></div>
          {recent.length ? <div className="overview-alert-list">{recent.map((alert: ApiData) => <div className="overview-alert-row" key={alert.id}><span className={`overview-alert-icon ${alert.severity}`}><AlertCircle size={15} /></span><div><b>{alert.engine_id} <Badge tone={alert.severity}>{severityLabel(alert.severity)}</Badge></b><small>Estimated {number(alert.predicted_rul, 1)} cycles · cycle {number(alert.cycle)}</small></div>{alert.status === 'open' && <button className="ack-button" onClick={() => acknowledge(alert.id)}>Acknowledge</button>}</div>)}</div> : <div className="overview-empty">No open threshold alerts.</div>}
        </section>

        <section className="panel data-provenance-panel"><Database size={16} /><div><b>{data.dataset?.name || 'Selected dataset'} · {data.dataset?.subset || '—'}</b><span>{data.dataset?.source || 'Dataset source unavailable'} · {sourceNote}</span></div></section>
      </div>
    </section>
  </div>
}

function EngineScreen({ engine, engines, selectedId, setSelected, startReplay }: any) {
  const [detail, setDetail] = useState<ApiData | null>(null)
  const [sensor, setSensor] = useState('sensor_2')
  useEffect(() => { if (selectedId) void api(`/engines/${selectedId}/history`).then(setDetail).catch(() => setDetail(null)) }, [selectedId])
  return <>
    <PageHeading eyebrow="WORKSPACE · ASSET DETAIL" title="Engine health" detail="Inspect observed sensor history and current model estimates." tag={<Badge tone="demo">RESEARCH DATA</Badge>} action={<button className="primary-button" onClick={() => startReplay()}><Play size={15} fill="currentColor" /> Replay engine</button>} />
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
      {!replay ? <div className="replay-empty"><div className="replay-empty-icon"><Waves size={26} /></div><h3>Replay a simulated engine</h3><p>Each observation is sent through the active model. Predictions are stored with the model version and checked against configured alert thresholds.</p><div className="replay-controls"><div className="select-wrap"><Cpu size={15} /><select value={selectedEngine} onChange={(event) => setSelected(event.target.value)}>{engines.map((item: any) => <option key={item.id} value={item.id}>{item.id}</option>)}</select><ChevronDown size={15} /></div><button className="primary-button" onClick={() => start()}><Play size={15} fill="currentColor" /> Start replay</button></div></div> : <>
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
