import { useCallback, useEffect, useState, type ReactNode } from 'react'
import { API_MODE, api } from './api/client'
import type { AgentCase, Comparison, TopicSummary } from './api/types'
import { AgentPanel } from './components/AgentPanel'
import { CasesPage } from './components/CasesPage'
import { ChangesView } from './components/ChangesView'
import { Headword } from './components/Headword'
import { Icon } from './components/Icon'
import { Landing } from './components/Landing'
import { MatchStrip } from './components/MatchStrip'
import { ReadingPane, type PassageFocus, type Side } from './components/ReadingPane'
import { SourcesPage } from './components/SourcesPage'
import { NARROW, WIDE, useMediaQuery } from './lib/useMediaQuery'
import { useAgentChat } from './lib/useAgentChat'
import styles from './App.module.css'

type Status = 'idle' | 'loading' | 'ready' | 'notfound' | 'error'
type Panel = 'read' | 'changes' | 'ask'
type Page = 'compare' | 'cases' | 'sources'

const PAGES: { id: Page; label: string; short?: string }[] = [
  { id: 'compare', label: 'Compare' },
  { id: 'cases', label: 'Agent cases', short: 'Cases' },
  { id: 'sources', label: 'Data and models', short: 'Data' },
]

const params = () => new URLSearchParams(window.location.search)
const pageFromUrl = (): Page => {
  const p = params().get('page')
  return p === 'cases' || p === 'sources' ? p : 'compare'
}

const COLLAPSE_KEY = 'kat.agentHidden'
const readCollapsed = () => {
  try {
    return localStorage.getItem(COLLAPSE_KEY) === '1'
  } catch {
    return false
  }
}

export default function App() {
  const wide = useMediaQuery(WIDE)
  const narrow = useMediaQuery(NARROW)

  const [page, setPage] = useState<Page>(pageFromUrl)
  const [topics, setTopics] = useState<TopicSummary[]>([])
  const [input, setInput] = useState(() => params().get('q') ?? '')
  const [comparison, setComparison] = useState<Comparison | null>(null)
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState('')
  const [lastQuery, setLastQuery] = useState('')

  const [panel, setPanel] = useState<Panel>('read')
  const [side, setSide] = useState<Side>('britannica')
  const [activeId, setActiveId] = useState<string | null>(null)
  const [focus, setFocus] = useState<PassageFocus | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [agentHidden, setAgentHidden] = useState(readCollapsed)

  const chat = useAgentChat()

  const hideAgent = (hidden: boolean) => {
    setAgentHidden(hidden)
    try {
      localStorage.setItem(COLLAPSE_KEY, hidden ? '1' : '0')
    } catch {
      // Storage blocked: the choice lasts for this visit only.
    }
  }

  useEffect(() => {
    api.topics().then(setTopics, () => setTopics([]))
  }, [])

  const pushUrl = (next: { page?: Page; q?: string | null }) => {
    const url = new URL(window.location.href)
    if (next.page) {
      if (next.page === 'compare') url.searchParams.delete('page')
      else url.searchParams.set('page', next.page)
    }
    if (next.q === null) url.searchParams.delete('q')
    else if (next.q !== undefined) url.searchParams.set('q', next.q)
    window.history.pushState(null, '', url)
  }

  const load = useCallback(async (query: string) => {
    const q = query.trim()
    if (!q) {
      setStatus('idle')
      setComparison(null)
      return
    }
    setLastQuery(q)
    setStatus('loading')
    setActiveId(null)
    setFocus(null)
    try {
      const c = await api.compare(q)
      if (!c) {
        setComparison(null)
        setStatus('notfound')
        return
      }
      setComparison(c)
      setInput(c.topic.label)
      setPanel((p) => (p === 'ask' ? 'ask' : 'read'))
      setSide('britannica')
      setStatus('ready')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Something went wrong.')
      setStatus('error')
    }
  }, [])

  useEffect(() => {
    const sync = () => {
      const q = params().get('q') ?? ''
      setPage(pageFromUrl())
      setInput(q)
      load(q)
    }
    sync()
    window.addEventListener('popstate', sync)
    return () => window.removeEventListener('popstate', sync)
  }, [load])

  const search = (q: string) => {
    pushUrl({ page: 'compare', q })
    setPage('compare')
    load(q)
  }

  const goPage = (p: Page) => {
    pushUrl({ page: p })
    setPage(p)
  }

  const goHome = () => {
    pushUrl({ page: 'compare', q: null })
    setPage('compare')
    setInput('')
    setComparison(null)
    setStatus('idle')
  }

  const showPassage = (passageId: string) => {
    setPanel('read')
    setActiveId(null)
    if (!wide) setDrawerOpen(false)
    setFocus({ passageId, nonce: Date.now() })
  }

  const showAlignment = (id: string) => {
    setPanel('read')
    setActiveId(id)
  }

  const replay = async (c: AgentCase) => {
    pushUrl({ page: 'compare', q: c.topic })
    setPage('compare')
    await load(c.topic)
    if (narrow) setPanel('ask')
    else if (wide) hideAgent(false)
    else setDrawerOpen(true)
    chat.ask(c.topic, c.question)
  }

  const inWorkspace = page === 'compare' && status !== 'idle'
  const ready = status === 'ready' && comparison
  const topicKey = comparison?.topic.label ?? ''
  const agent = comparison && (
    <AgentPanel
      comparison={comparison}
      messages={chat.threads[topicKey] ?? []}
      pending={chat.pending === topicKey}
      onAsk={(q) => chat.ask(topicKey, q)}
      onClear={() => chat.clear(topicKey)}
      onCite={showPassage}
      onCollapse={wide ? () => hideAgent(true) : undefined}
      onClose={!wide && !narrow ? () => setDrawerOpen(false) : undefined}
    />
  )

  return (
    <div className={styles.app}>
      <header className={styles.masthead}>
        <button type="button" className={styles.wordmark} onClick={goHome}>
          Knowledge Across Time
        </button>

        {inWorkspace && (
          <div className={styles.search}>
            <Headword topics={topics} value={input} onChange={setInput} onSubmit={search} size="compact" />
          </div>
        )}

        <nav className={styles.nav} aria-label="Pages">
          {API_MODE === 'demo' && (
            <span className={styles.demo} title="Built-in demo data. Set VITE_API_MODE=live to use the backend.">
              Demo data
            </span>
          )}
          {PAGES.map((p) => (
            <button key={p.id} type="button" className={styles.navItem} aria-current={page === p.id ? 'page' : undefined} onClick={() => goPage(p.id)}>
              {p.short ? (
                <>
                  <span className={styles.hideNarrow}>{p.label}</span>
                  <span className={styles.showNarrow}>{p.short}</span>
                </>
              ) : (
                p.label
              )}
            </button>
          ))}
        </nav>
      </header>

      {page === 'cases' && <CasesPage onReplay={replay} />}
      {page === 'sources' && <SourcesPage />}

      {page === 'compare' && !inWorkspace && <Landing topics={topics} input={input} onInput={setInput} onSearch={search} />}

      {inWorkspace && (
        <main className={`${styles.workspace} ${wide ? (agentHidden ? styles.withRail : styles.withAgent) : ''}`}>
          <div className={styles.main}>
            {ready && (
              <MatchStrip
                key={comparison.topic.slug}
                comparison={comparison}
                actions={
                  !wide && !narrow ? (
                    <button type="button" className="btn" onClick={() => setDrawerOpen(true)}>
                      Ask the agent
                    </button>
                  ) : undefined
                }
              >
                <div className={styles.tabs} role="tablist" aria-label="View">
                  {narrow ? (
                    <>
                      <Tab selected={panel === 'read' && side === 'britannica'} onClick={() => (setPanel('read'), setSide('britannica'))}>
                        <span className="num">{comparison.britannica.year}</span>
                      </Tab>
                      <Tab selected={panel === 'read' && side === 'wikipedia'} onClick={() => (setPanel('read'), setSide('wikipedia'))}>
                        Today
                      </Tab>
                      <Tab selected={panel === 'changes'} onClick={() => setPanel('changes')}>
                        Changes
                      </Tab>
                      <Tab selected={panel === 'ask'} onClick={() => setPanel('ask')}>
                        Ask
                      </Tab>
                    </>
                  ) : (
                    <>
                      <Tab selected={panel !== 'changes'} onClick={() => setPanel('read')}>
                        Side by side
                      </Tab>
                      <Tab selected={panel === 'changes'} onClick={() => setPanel('changes')}>
                        What changed
                      </Tab>
                    </>
                  )}
                </div>
              </MatchStrip>
            )}

            <div className={styles.stage}>
              {status === 'loading' && <Loading query={lastQuery} />}
              {status === 'notfound' && <NotFound query={lastQuery} topics={topics} onSearch={search} />}
              {status === 'error' && (
                <div className={styles.message}>
                  <h2>The comparison did not load</h2>
                  <p>{error}</p>
                  <button type="button" className="btn" onClick={() => load(lastQuery)}>
                    Try again
                  </button>
                </div>
              )}
              {ready &&
                (narrow && panel === 'ask' ? (
                  <div className={styles.askPanel}>{agent}</div>
                ) : panel === 'changes' ? (
                  <ChangesView comparison={comparison} onShow={showAlignment} />
                ) : (
                  <ReadingPane
                    comparison={comparison}
                    activeId={activeId}
                    onActivate={setActiveId}
                    focus={focus}
                    narrow={narrow}
                    side={side}
                    onSideChange={setSide}
                  />
                ))}
            </div>
          </div>

          {wide && ready && !agentHidden && <aside className={styles.agent}>{agent}</aside>}
          {wide && ready && agentHidden && (
            <aside className={styles.rail}>
              <button type="button" className={styles.railBtn} onClick={() => hideAgent(false)} aria-label="Show the agent">
                <Icon name="panelShow" />
                <span className={styles.railText}>Ask the agent</span>
                {(chat.threads[topicKey]?.length ?? 0) > 0 && <span className={styles.railDot} aria-hidden="true" />}
              </button>
            </aside>
          )}
        </main>
      )}

      {!wide && !narrow && drawerOpen && ready && (
        <div className={styles.drawerWrap}>
          <button type="button" className={styles.backdrop} aria-label="Close the agent" onClick={() => setDrawerOpen(false)} />
          <aside className={styles.drawer}>{agent}</aside>
        </div>
      )}
    </div>
  )
}

function Tab({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button type="button" role="tab" aria-selected={selected} className={styles.tab} onClick={onClick}>
      {children}
    </button>
  )
}

function Loading({ query }: { query: string }) {
  return (
    <div className={styles.message} role="status">
      <p className={styles.loadingWord}>{query.toUpperCase()}</p>
      <p>Finding the Britannica page and its closest Wikipedia article…</p>
    </div>
  )
}

function NotFound({ query, topics, onSearch }: { query: string; topics: TopicSummary[]; onSearch: (q: string) => void }) {
  return (
    <div className={styles.message}>
      <h2>No indexed page for “{query}”</h2>
      <p>The index holds {topics.length || 'a sample of'} Britannica pages. Try one of these:</p>
      <div className={styles.chips}>
        {topics.map((t) => (
          <button key={t.slug} type="button" className="btn" onClick={() => onSearch(t.label)}>
            {t.label}
          </button>
        ))}
      </div>
    </div>
  )
}
