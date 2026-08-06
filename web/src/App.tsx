import { useCallback, useEffect, useRef, useState } from 'react'
import { DemoDef, DEMO_SLUGS, getDemos } from './config'
import { getStoredLang, Lang, storeLang, STRINGS, Strings } from './i18n'
import { parseRoute, pushRoute, ROBOTS_ROUTE, slugToPath } from './routes'
import { getToken, login, logout } from './services/auth'
import { AgentEvent, DemoSession, newSessionId } from './services/events'

interface ChatMsg {
  role: 'user' | 'agent' | 'error'
  text: string
}

interface Metrics {
  cycles: number
  total_tokens: number
  input_tokens: number
  output_tokens: number
  duration_s: number
}

// Nova emits <thinking>…</thinking> inline; keep it out of the chat bubble.
function stripThinking(text: string): string {
  return text.replace(/<thinking>[\s\S]*?(<\/thinking>|$)/g, '').trimStart()
}

function LangSwitch({ lang, onChange }: { lang: Lang; onChange: (l: Lang) => void }) {
  return (
    <div className="langswitch">
      {(['en', 'es', 'pt'] as Lang[]).map((l) => (
        <button
          key={l}
          className={l === lang ? 'active' : ''}
          onClick={() => onChange(l)}
        >
          {l.toUpperCase()}
        </button>
      ))}
    </div>
  )
}

function Login({
  t,
  lang,
  onLang,
  onDone,
}: {
  t: Strings
  lang: Lang
  onLang: (l: Lang) => void
  onDone: () => void
}) {
  const [user, setUser] = useState('kiosk')
  const [pass, setPass] = useState('')
  const [err, setErr] = useState('')
  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      await login(user, pass)
      onDone()
    } catch (ex) {
      setErr(ex instanceof Error ? ex.message : 'Error')
    }
  }
  return (
    <form className="login" onSubmit={submit}>
      <h1>
        Strands <span>Agents</span> Demos
      </h1>
      <LangSwitch lang={lang} onChange={onLang} />
      <input value={user} onChange={(e) => setUser(e.target.value)} placeholder={t.username} />
      <input
        type="password"
        value={pass}
        onChange={(e) => setPass(e.target.value)}
        placeholder={t.password}
      />
      {err && <div className="err">{err}</div>}
      <button type="submit">{t.signIn}</button>
    </form>
  )
}

function CycleCard({ event, t }: { event: AgentEvent; t: Strings }) {
  const [open, setOpen] = useState(false)
  const reasoning = typeof event.reasoning === 'string' ? event.reasoning.trim() : ''
  return (
    <div
      className={`card cycle ${reasoning ? 'expandable' : ''}`}
      onClick={() => reasoning && setOpen(!open)}
    >
      <div className="label">
        {t.cycleLabel}
        {reasoning && <span className="chevron">{open ? '▾' : '▸'}</span>}
      </div>
      {reasoning
        ? <>{t.reasoning(String(event.cycle))}<span className="hint"> — {open ? '' : t.clickToSee}</span></>
        : <span className="cycle-num">{t.cycleLabel} {String(event.cycle)}</span>
      }
      {open && reasoning && <div className="reasoning">{reasoning}</div>}
    </div>
  )
}

function InsightCard({ event, t }: { event: AgentEvent; t: Strings }) {
  switch (event.type) {
    case 'cycle_start':
      return <CycleCard event={event} t={t} />
    case 'tool_call_start':
      return (
        <div className="card tool">
          <div className="label">{t.toolCall}</div>
          <strong>{String(event.tool)}</strong>
          <div className="mono">{String(event.input ?? '')}</div>
        </div>
      )
    case 'tool_result':
      return (
        <div className="card result">
          {event.duration_ms != null && <span className="ms">{String(event.duration_ms)} ms</span>}
          <div className="label">{t.result}</div>
          <strong>{String(event.tool)}</strong>
          <div className="mono">{String(event.output ?? '')}</div>
        </div>
      )
    case 'hook_blocked':
      return (
        <div className="card blocked">
          <div className="label">{t.blocked}</div>
          <strong>{String(event.tool)}</strong> — {String(event.reason)}
          <div className="mono">hook: {String(event.hook)}</div>
        </div>
      )
    case 'structured': {
      const fields = (event.fields ?? {}) as Record<string, unknown>
      return (
        <div className="card result">
          <div className="label">📋 {t.structuredLabel}</div>
          <table className="fields">
            <tbody>
              {Object.entries(fields).map(([k, v]) => (
                <tr key={k}>
                  <td className="fieldname">{k}</td>
                  <td className={v == null || (Array.isArray(v) && v.length === 0) ? 'null' : 'ok'}>
                    {v == null
                      ? 'null'
                      : Array.isArray(v)
                        ? v.join(', ') || '—'
                        : String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
    }
    case 'node_start':
      return (
        <div className="card cycle">
          <div className="label">🤖 {t.nodeActive}</div>
          <strong>{String(event.node)}</strong>
        </div>
      )
    case 'handoff':
      return (
        <div className="card tool">
          <div className="label">🔀 Handoff</div>
          <strong>{String(event.from_agent)}</strong> → <strong>{String(event.to_agent)}</strong>
        </div>
      )
    case 'swarm_metrics': {
      const nodes = (event.nodes ?? {}) as Record<string, { total_tokens?: number }>
      return (
        <div className="card result">
          <div className="label">🐝 {t.swarmSummary}</div>
          <div className="mono">{(event.node_history as string[])?.join(' → ')}</div>
          {Object.entries(nodes).map(([id, u]) => (
            <div key={id}>
              {id}: <strong>{u.total_tokens ?? '—'}</strong> tokens
            </div>
          ))}
        </div>
      )
    }
    case 'phase': {
      const phaseName =
        event.phase === 'naive'
          ? t.phaseNaive
          : event.phase === 'pointer'
            ? t.phasePointer
            : event.phase === 'chaos_naive'
              ? t.phaseChaosNaive
              : t.phaseChaosResilient
      const bad = event.phase === 'naive' || event.phase === 'chaos_naive'
      return (
        <div className="card cycle">
          <div className="label">{bad ? '🔴' : '🟢'} {t.phaseRunning}</div>
          <strong>{phaseName}</strong>
        </div>
      )
    }
    case 'chaos_injected':
      return (
        <div className="card blocked">
          <div className="label">💥 {t.chaosInjected}</div>
          <strong>{String(event.tool)}</strong> — {String(event.effect)}
          <div className="mono">{String(event.detail ?? '')}</div>
        </div>
      )
    case 'recovered':
      return (
        <div className="card result">
          <div className="label">🛟 {t.recovered}</div>
          <strong>{String(event.tool)}</strong> — {String(event.action)}
          <div className="mono">{String(event.detail ?? '')}</div>
        </div>
      )
    case 'phase_result':
      return (
        <div className="card tool">
          <div className="label">{event.phase === 'naive' ? '🔴' : '🟢'} {t.phaseDone}</div>
          <strong>{event.phase === 'naive' ? t.phaseNaive : t.phasePointer}</strong>:{' '}
          {Number(event.total_tokens).toLocaleString()} tokens
        </div>
      )
    case 'interrupt':
      return (
        <div className="card blocked">
          <div className="label">🧊 Interrupt</div>
          <strong>{String(event.name)}</strong>
          <div className="mono">{JSON.stringify(event.reason)}</div>
        </div>
      )
    case 'business_attr': {
      const attrs = (event.attrs ?? {}) as Record<string, unknown>
      const vip = attrs['business.vip_booking'] === true
      return (
        <div className="card result">
          <div className="label">{vip ? '💎' : '🏷️'} {t.businessAttr}</div>
          {Object.entries(attrs).map(([k, v]) => (
            <div key={k} className="mono">
              {k} = {String(v)}
            </div>
          ))}
        </div>
      )
    }
    case 'ground_truth': {
      const bookings = (event.bookings ?? []) as Array<Record<string, unknown>>
      return (
        <div className="card cycle">
          <div className="label">📒 {t.groundTruth}</div>
          {bookings.length === 0
            ? t.groundTruthEmpty
            : bookings.map((b, i) => (
                <div key={i} className="mono">
                  {String(b.id)} · {String(b.offer_id)} · ${String(b.price_usd)}
                </div>
              ))}
        </div>
      )
    }
    case 'node_stop':
      return (
        <div className="card result">
          <div className="label">✅ {t.nodeDone}</div>
          <strong>{String(event.node)}</strong>
        </div>
      )
    case 'graph_topology': {
      const edges = (event.edges ?? []) as string[][]
      return (
        <div className="card cycle">
          <div className="label">🗺️ {t.graphTopology}</div>
          {edges.map((e, i) => (
            <div key={i} className="mono">
              {e[0]} → {e[1]}
            </div>
          ))}
        </div>
      )
    }
    case 'comparison': {
      const naive = (event.naive ?? {}) as { total_tokens?: number }
      const pointer = (event.pointer ?? {}) as { total_tokens?: number }
      const max = Math.max(naive.total_tokens ?? 1, pointer.total_tokens ?? 1)
      return (
        <div className="card result comparison">
          <div className="label">⚖️ {t.comparisonLabel}</div>
          {[
            { name: t.phaseNaive, v: naive.total_tokens ?? 0, cls: 'naive' },
            { name: t.phasePointer, v: pointer.total_tokens ?? 0, cls: 'pointer' },
          ].map((row) => (
            <div key={row.cls} className="meter">
              <span className="metername">{row.name}</span>
              <div className="meterbar">
                <div className={`meterfill ${row.cls}`} style={{ width: `${(100 * row.v) / max}%` }} />
              </div>
              <span className="meterval">{row.v.toLocaleString()}</span>
            </div>
          ))}
          <div className="reduction">
            −{String(event.reduction_pct)}% {t.tokensSaved}
          </div>
        </div>
      )
    }
    case 'memory_state': {
      const notes = (event.notes ?? []) as string[]
      const sent = Number(event.emails_sent_this_turn ?? 0)
      return (
        <div className="card cycle">
          <div className="label">🧠 {t.memoryState}</div>
          {notes.length === 0 ? (
            <div className="mono">{t.memoryEmpty}</div>
          ) : (
            notes.map((n, i) => (
              <div key={i} className="mono poisoned">
                📝 {n}
              </div>
            ))
          )}
          <div className={sent === 0 ? 'reduction' : 'mono'}>
            {sent === 0 ? `🛡️ ${t.emailsBlocked}` : `⚠️ ${sent} ${t.emailsLeaked}`}
          </div>
        </div>
      )
    }
    default:
      return null
  }
}

export default function App() {
  const [lang, setLang] = useState<Lang>(getStoredLang())
  const [authed, setAuthed] = useState(!!getToken())
  // Initial demo/robots view come from the URL (e.g. /agent_loop, /hooks, /robots).
  const initialRoute = parseRoute(window.location.pathname, DEMO_SLUGS[0])
  const [demoSlug, setDemoSlug] = useState(initialRoute.slug)
  const [status, setStatus] = useState<'connecting' | 'ready' | 'closed' | 'error'>('closed')
  const [messages, setMessages] = useState<ChatMsg[]>([])
  const [insights, setInsights] = useState<AgentEvent[]>([])
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [showLupa, setShowLupa] = useState(false)
  const [pendingInterrupt, setPendingInterrupt] = useState<{
    id: string
    reason: unknown
  } | null>(null)
  const [showRobots, setShowRobots] = useState(initialRoute.robots)
  const sessionRef = useRef<DemoSession | null>(null)
  const feedRef = useRef<HTMLDivElement>(null)
  const msgsRef = useRef<HTMLDivElement>(null)
  const busyTimer = useRef<number | null>(null)

  const t = STRINGS[lang]
  const demos = getDemos(lang)
  const demo: DemoDef = demos.find((d) => d.slug === demoSlug) ?? demos[0]

  const changeLang = (l: Lang) => {
    storeLang(l)
    setLang(l)
  }

  // Navigate to a demo (or the robots slot) and reflect it in the address bar.
  const goToDemo = (slug: string) => {
    setShowRobots(false)
    setDemoSlug(slug)
    pushRoute(slugToPath(slug))
  }
  const goToRobots = () => {
    setShowRobots(true)
    pushRoute('/' + ROBOTS_ROUTE)
  }

  // Keep the view in sync with browser back/forward.
  useEffect(() => {
    const onPop = () => {
      const r = parseRoute(window.location.pathname, DEMO_SLUGS[0])
      setShowRobots(r.robots)
      setDemoSlug(r.slug)
    }
    window.addEventListener('popstate', onPop)
    return () => window.removeEventListener('popstate', onPop)
  }, [])

  const handleEvent = useCallback((e: AgentEvent) => {
    if (e.type === 'token') {
      setMessages((prev) => {
        const out = [...prev]
        const last = out[out.length - 1]
        if (last?.role === 'agent') {
          out[out.length - 1] = { ...last, text: last.text + String(e.text) }
        } else {
          out.push({ role: 'agent', text: String(e.text) })
        }
        return out
      })
    } else if (e.type === 'metrics') {
      setMetrics(e as unknown as Metrics)
    } else if (e.type === 'reasoning') {
      // Attach reasoning text to the matching cycle card in the insights feed.
      setInsights((prev) => {
        const out = [...prev]
        for (let i = out.length - 1; i >= 0; i--) {
          if (out[i].type === 'cycle_start' && out[i].cycle === e.cycle) {
            const existing = typeof out[i].reasoning === 'string' ? out[i].reasoning : ''
            out[i] = { ...out[i], reasoning: existing + String(e.text) }
            return out
          }
        }
        return out
      })
    } else if (e.type === 'interrupt') {
      setPendingInterrupt({ id: String(e.id), reason: e.reason })
      setInsights((prev) => [...prev, e])
    } else if (e.type === 'error') {
      setMessages((prev) => [...prev, { role: 'error', text: String(e.message) }])
    } else if (e.type === 'done') {
      setBusy(false)
      if (busyTimer.current) window.clearTimeout(busyTimer.current)
    } else {
      setInsights((prev) => [...prev, e])
    }
  }, [])

  const connect = useCallback(async () => {
    sessionRef.current?.close()
    const token = getToken()
    if (!token) {
      setAuthed(false)
      return
    }
    setMessages([])
    setInsights([])
    setMetrics(null)
    setBusy(false)
    const s = new DemoSession(token, demoSlug, newSessionId(), handleEvent, setStatus)
    sessionRef.current = s
    try {
      await s.connect()
    } catch {
      setStatus('error')
    }
  }, [demoSlug, handleEvent])

  useEffect(() => {
    if (authed) connect()
    return () => sessionRef.current?.close()
  }, [authed, connect])

  useEffect(() => {
    feedRef.current?.scrollTo({ top: feedRef.current.scrollHeight, behavior: 'smooth' })
  }, [insights])
  useEffect(() => {
    msgsRef.current?.scrollTo({ top: msgsRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const send = async (text: string) => {
    const prompt = text.trim()
    if (!prompt || busy || status !== 'ready') return
    setMessages((prev) => [...prev, { role: 'user', text: prompt }])
    setInput('')
    setBusy(true)
    // Watchdog: never leave the input locked forever if `done` gets lost.
    if (busyTimer.current) window.clearTimeout(busyTimer.current)
    busyTimer.current = window.setTimeout(() => setBusy(false), 120_000)
    try {
      await sessionRef.current!.send(prompt)
    } catch (ex) {
      setBusy(false)
      setMessages((prev) => [
        ...prev,
        { role: 'error', text: ex instanceof Error ? ex.message : t.sendFailed },
      ])
    }
  }

  if (!authed)
    return <Login t={t} lang={lang} onLang={changeLang} onDone={() => setAuthed(true)} />

  const categories = [...new Set(demos.map((d) => d.category))]

  return (
    <>
      <header className="topbar">
        <div className="logo">
          Strands <span>Agents</span> · Demos
        </div>
        <div className={`status ${status}`}>
          {status === 'ready' ? t.connected : status === 'connecting' ? t.connecting : t.disconnected}
        </div>
        <LangSwitch lang={lang} onChange={changeLang} />
        <button className="reset" onClick={connect}>
          {t.restart}
        </button>
        <button
          className="reset"
          onClick={() => {
            logout()
            setAuthed(false)
          }}
        >
          {t.signOut}
        </button>
        <div className="credits">
          <a
            href="https://github.com/elizabethfuentes12/strands-agents-demo-sample-for-aws"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
          <span>·</span>
          <a href="https://strandsagents.com/" target="_blank" rel="noreferrer">
            strandsagents.com
          </a>
        </div>
      </header>

      <div className="layout">
        <nav className="menu">
          {categories.map((cat) => (
            <div key={cat}>
              <div className="category">{cat}</div>
              {demos
                .filter((d) => d.category === cat)
                .map((d) => (
                  <button
                    key={d.slug}
                    className={`item ${d.slug === demo.slug && !showRobots ? 'active' : ''}`}
                    onClick={() => goToDemo(d.slug)}
                  >
                    {d.title}
                  </button>
                ))}
            </div>
          ))}
          <div className="category">🤖 Robots</div>
          <button
            className={`item ${showRobots ? 'active' : ''}`}
            onClick={goToRobots}
          >
            {t.robotsTitle}
          </button>
        </nav>

        {showRobots ? (
          <section className="robots">
            <h2>🤖 {t.robotsTitle}</h2>
            <p>{t.robotsBody}</p>
            {/* Video slot: replace the placeholder below with an embedded
                video of Strands running on a physical robot, e.g.
                <video src="/robots-demo.mp4" controls /> or a YouTube iframe. */}
            <div className="videoslot">
              <span>🎬 {t.robotsVideoSoon}</span>
            </div>
            <p className="dim">{t.robotsHint}</p>
          </section>
        ) : (
          <>
        <section className="chat">
          <div className="messages" ref={msgsRef}>
            {messages.length === 0 && <div className="bubble agent">{demo.description}</div>}
            {messages.map((m, i) => (
              <div key={i} className={`bubble ${m.role}`}>
                {m.role === 'agent' ? stripThinking(m.text) : m.text}
              </div>
            ))}
          </div>
          {busy && !pendingInterrupt && <div className="typing">{t.working}</div>}
          {pendingInterrupt && (
            <div className="interruptbar">
              <div className="frozen">🧊 {t.approvalNeeded}</div>
              <div className="mono">{JSON.stringify(pendingInterrupt.reason)}</div>
              <div className="actions">
                <button
                  className="approve"
                  onClick={() => {
                    const id = pendingInterrupt.id
                    setPendingInterrupt(null)
                    setBusy(true)
                    sessionRef.current?.respondToInterrupt(id, 'y')
                  }}
                >
                  {t.approve}
                </button>
                <button
                  className="rejectbtn"
                  onClick={() => {
                    const id = pendingInterrupt.id
                    setPendingInterrupt(null)
                    setBusy(true)
                    sessionRef.current?.respondToInterrupt(id, 'no')
                  }}
                >
                  {t.reject}
                </button>
              </div>
            </div>
          )}
          <div className="suggestions">
            {demo.suggestions.map((s) => (
              <button key={s} onClick={() => send(s)} disabled={busy}>
                {s}
              </button>
            ))}
          </div>
          <div className="inputrow">
            <input
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && send(input)}
              placeholder={t.typeMessage}
            />
            <button onClick={() => send(input)} disabled={busy || status !== 'ready'}>
              {t.send}
            </button>
          </div>
        </section>

        <aside className="insights">
          <div className="head">
            <h2>{t.underHood}</h2>
            <button className="lupa" onClick={() => setShowLupa(true)}>
              {t.whyInteresting}
            </button>
          </div>
          <div className="feed" ref={feedRef}>
            {insights.length === 0 && (
              <div className="card">
                <div className="label">{t.waiting}</div>
                {t.waitingBody}
              </div>
            )}
            {insights.map((e, i) => (
              <InsightCard key={i} event={e} t={t} />
            ))}
          </div>
          {metrics && (
            <div className="metricsbar">
              <div className="metric">
                <div className="value">{metrics.cycles}</div>
                <div className="name">{t.cycles}</div>
              </div>
              <div className="metric">
                <div className="value">{metrics.total_tokens}</div>
                <div className="name">{t.tokens}</div>
              </div>
              <div className="metric">
                <div className="value">{metrics.duration_s}s</div>
                <div className="name">{t.duration}</div>
              </div>
              <div className="metric">
                <div className="value">{metrics.output_tokens}</div>
                <div className="name">{t.output}</div>
              </div>
            </div>
          )}
        </aside>
          </>
        )}
      </div>

      {showLupa && (
        <div className="overlay" onClick={() => setShowLupa(false)}>
          <div className="panel" onClick={(e) => e.stopPropagation()}>
            <h3>{t.whyTitle(demo.title)}</h3>
            <ul>
              {demo.why.map((w) => (
                <li key={w}>{w}</li>
              ))}
            </ul>
            <pre>{demo.code}</pre>
            <div className="overlay-actions">
              <a href={demo.docsUrl} target="_blank" rel="noreferrer" className="docslink">
                {t.readDocs} ↗
              </a>
              <button onClick={() => setShowLupa(false)}>{t.gotIt}</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
