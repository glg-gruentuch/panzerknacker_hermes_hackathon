import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Meta } from '../api/types'
import { Icon } from './Icon'
import styles from './Pages.module.css'

const MISSING = 'Not recorded yet'

function Value({ text }: { text: string }) {
  return text.startsWith(MISSING) ? <span className={styles.missing}>{text}</span> : <>{text}</>
}

/** Dataset versions, the models in the pipeline, and how the sample was chosen. */
export function SourcesPage() {
  const [meta, setMeta] = useState<Meta | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.meta().then(setMeta, (e: unknown) => setError(e instanceof Error ? e.message : 'The sources did not load.'))
  }, [])

  return (
    <main className={styles.page}>
      <h1 className={styles.title}>Data and models</h1>
      <p className={styles.lede}>What every comparison is built from, recorded so the results can be reproduced.</p>
      {error && <p className={styles.notice}>{error}</p>}
      {!meta && !error && <p className={styles.lede}>Loading…</p>}

      {meta && (
        <>
          <section className={styles.block} aria-labelledby="src-datasets">
            <h2 id="src-datasets" className={styles.blockTitle}>
              Datasets
            </h2>
            {meta.datasets.map((d) => (
              <div key={d.name} className={styles.dataset}>
                <a href={d.url} target="_blank" rel="noreferrer" className={styles.datasetName}>
                  {d.name} <Icon name="external" size={13} />
                </a>
                <p className={styles.datasetSource}>{d.source}</p>
                <dl className={styles.kv}>
                  <dt>Version</dt>
                  <dd className="num">
                    <Value text={d.version} />
                  </dd>
                  <dt>Downloaded</dt>
                  <dd className="num">
                    <Value text={d.downloaded} />
                  </dd>
                </dl>
              </div>
            ))}
          </section>

          <section className={styles.block} aria-labelledby="src-models">
            <h2 id="src-models" className={styles.blockTitle}>
              Pipeline
            </h2>
            <ol className={styles.pipeline}>
              {meta.models.map((m) => (
                <li key={m.name}>
                  <span className={styles.role}>{m.role}</span>
                  <span className={styles.modelName}>{m.name}</span>
                  <span className={styles.host}>{m.host}</span>
                </li>
              ))}
            </ol>
          </section>

          <section className={styles.block} aria-labelledby="src-sample">
            <h2 id="src-sample" className={styles.blockTitle}>
              Sample of {meta.sample.size} Britannica pages
            </h2>
            <p className={styles.method}>
              <Value text={meta.sample.method} />
            </p>
          </section>
        </>
      )}
    </main>
  )
}
