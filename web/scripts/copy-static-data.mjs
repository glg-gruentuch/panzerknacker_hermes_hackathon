// Copies the static data and the page scans into a built app, for VITE_API_MODE=static.
// Usage: node scripts/copy-static-data.mjs <dist>
//   web/static-data/                         -> <dist>/data/
//   deliverables/website/assets/scans/*.jpg  -> <dist>/scans/
import { cpSync, existsSync, readFileSync } from 'node:fs'
import { join } from 'node:path'

const dist = process.argv[2] ?? 'dist'
const data = 'static-data'
const scans = '../deliverables/website/assets/scans'

for (const dir of [data, scans]) {
  if (!existsSync(dir)) {
    console.error(`Missing ${dir}. Run web/scripts/export-static.py, or check out the deliverables.`)
    process.exit(1)
  }
}
cpSync(data, join(dist, 'data'), { recursive: true })
cpSync(scans, join(dist, 'scans'), { recursive: true })
const source = JSON.parse(readFileSync(join(data, 'SOURCE.json'), 'utf8'))
console.log(`Copied ${source.entries} comparisons from commit ${source.commit.slice(0, 7)} and the scans into ${dist}/`)
