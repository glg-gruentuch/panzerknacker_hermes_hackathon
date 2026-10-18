// Writes example API responses from the demo data to api-examples/.
// The backend team can diff their real responses against these.
import { mkdir, writeFile } from 'node:fs/promises'
import { createServer } from 'vite'

const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
try {
  const demo = await vite.ssrLoadModule('/src/api/demo/index.ts')
  const examples = {
    'GET topics.json': { topics: await demo.topics() },
    'GET compare?q=blood.json': await demo.compare('blood'),
    'GET compare?q=animal spirits.json': await demo.compare('animal spirits'),
    'POST chat.json': {
      request: { topic: 'Blood', question: 'Which facts about blood survived from 1797 to today?', history: [] },
      response: await demo.ask({ topic: 'Blood', question: 'Which facts about blood survived from 1797 to today?', history: [] }),
    },
    'GET cases.json': { cases: await demo.cases() },
    'GET meta.json': await demo.meta(),
  }
  await mkdir('api-examples', { recursive: true })
  for (const [name, body] of Object.entries(examples)) {
    const file = name.replace(/^(GET|POST) /, '').replace(/[?= ]/g, (c) => ({ '?': '_', '=': '-', ' ': '-' })[c])
    await writeFile(`api-examples/${file}`, JSON.stringify(body, null, 2) + '\n')
    console.log(`api-examples/${file}`)
  }
} finally {
  await vite.close()
}
