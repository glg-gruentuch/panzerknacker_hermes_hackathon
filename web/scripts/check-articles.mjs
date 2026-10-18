// Checks every file in articles/ before the site is built. `npm run build`
// runs it first, so a broken article stops the Cloudflare deploy and the
// current site stays live. Run it yourself with `npm run check-articles`.
import { readdir, readFile } from 'node:fs/promises'
import { createServer } from 'vite'

const files = (await readdir('articles')).filter((f) => f.endsWith('.json')).sort()
const entries = []
const problems = new Map()
for (const file of files) {
  const slug = file.slice(0, -'.json'.length)
  try {
    entries.push([slug, JSON.parse(await readFile(`articles/${file}`, 'utf8'))])
  } catch (err) {
    problems.set(slug, [`not valid JSON (${err.message})`])
  }
}

const vite = await createServer({ server: { middlewareMode: true }, appType: 'custom', logLevel: 'error' })
try {
  const { validateArticles } = await vite.ssrLoadModule('/src/api/demo/article.ts')
  for (const [slug, errors] of validateArticles(entries)) problems.set(slug, errors)
} finally {
  await vite.close()
}

if (problems.size) {
  for (const [slug, errors] of problems) console.error(`\narticles/${slug}.json\n  ${errors.join('\n  ')}`)
  console.error(`\n${problems.size} of ${files.length} article files have problems. Fix them and run \`npm run check-articles\` again.`)
  process.exit(1)
}
console.log(`All ${files.length} article files are fine.`)
