import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { parseGitHubActivity } from '../src/lib/github-profile.mjs'

const report = `Last 7 days (including today)
2026-10-28 - 2026-11-03 (Asia/Shanghai)
Total Time: 6 hrs 37 mins

Other        4 hrs 17 mins  █████████████░░░░░░░   64.81%`
const readme = `Unrelated content
<!--START_SECTION:obsidian-->
🔮 Time @Obsidian · **41 mins** in the last 7 days
<!--END_SECTION:obsidian-->
<!--START_SECTION:waka-->
\`\`\`txt
${report}
\`\`\`
<!--END_SECTION:waka-->`

test('extracts only dated public activity blocks, preserving the reported period', () => {
  assert.deepEqual(parseGitHubActivity(readme), {
    obsidian: 'Time @Obsidian · 41 mins in the last 7 days',
    weekly: report,
    periodStart: '2026-10-28', periodEnd: '2026-11-03'
  })
})

test('rejects missing or malformed reports so the existing snapshot can remain visible', () => {
  for (const source of ['', '<html>Unavailable</html>', readme.replace('2026-10-28 - 2026-11-03', 'unknown dates'), readme.replace('<!--END_SECTION:waka-->', '')]) {
    assert.throws(() => parseGitHubActivity(source))
  }
})

test('requires known statistics rather than treating arbitrary README HTML as report data', () => {
  assert.throws(() => parseGitHubActivity(readme.replace('Total Time: 6 hrs 37 mins', '<img src=x onerror=alert(1)>')))
  assert.throws(() => parseGitHubActivity(readme.replace('**41 mins**', '**<script>bad</script>**')))
})

test('accepts the producer’s no-activity reports without retaining stale usage', () => {
  const empty = readme.replace('**41 mins** in the last 7 days', 'No activity tracked in the last 7 days yet.').replace('Total Time: 6 hrs 37 mins', 'Total Time: 0 secs')
  assert.equal(parseGitHubActivity(empty).obsidian, 'Time @Obsidian · No activity tracked in the last 7 days yet.')
  assert.match(parseGitHubActivity(empty).weekly, /Total Time: 0 secs/)
})

function client(fetch, pendingImage = false) {
  const nodes = Object.fromEntries(['obsidian', 'weekly', 'snapshot', 'refresh'].map(key => [`[data-github-${key}]`, { textContent: `saved ${key}` }]))
  const events = {}
  const img = { hidden: false, complete: !pendingImage, naturalWidth: 0, addEventListener: (name, callback) => { events[name] = callback } }
  const fallback = { hidden: true }
  const root = { querySelector: key => nodes[key], querySelectorAll: () => [{ querySelector: key => key === 'img' ? img : fallback }] }
  const compiled = ts.transpile(readFileSync(new URL('../src/scripts/github-profile.ts', import.meta.url), 'utf8'), { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 })
  const exports = {}, timers = new Map()
  let timerId = 0
  vm.runInNewContext(compiled, { exports, require: () => ({ parseGitHubActivity }), AbortController, fetch,
    setTimeout: fn => { timers.set(++timerId, fn); return timerId }, clearTimeout: id => timers.delete(id) })
  const done = exports.setupGitHubProfile(root)
  return { nodes, img, fallback, done, timers, events }
}

test('client updates public activity text and dates, and recovers already broken images', async () => {
  const h = client(async (_url, options) => {
    assert.equal(options.credentials, 'omit')
    return { ok: true, text: async () => readme }
  })
  assert.equal(h.nodes['[data-github-refresh]'].textContent, 'Checking GitHub for updates…')
  await h.done
  assert.equal(h.nodes['[data-github-weekly]'].textContent, report)
  assert.equal(h.nodes['[data-github-obsidian]'].textContent, '41 mins in the last 7 days')
  assert.equal(h.nodes['[data-github-snapshot]'].hidden, true)
  assert.equal(h.nodes['[data-github-refresh]'].textContent, '')
  assert.equal(h.img.hidden, true)
  assert.equal(h.fallback.hidden, false)
  assert.equal(h.timers.size, 0)
})

test('network, HTTP and malformed README failures preserve all saved activity text', async () => {
  for (const fetch of [async () => { throw Error('offline') }, async () => ({ ok: false }), async () => ({ ok: true, text: async () => '<html>Unavailable</html>' })]) {
    const h = client(fetch)
    await h.done
    for (const key of ['obsidian', 'weekly', 'snapshot']) assert.equal(h.nodes[`[data-github-${key}]`].textContent, `saved ${key}`)
    assert.match(h.nodes['[data-github-refresh]'].textContent, /showing the saved snapshot/)
    assert.equal(h.timers.size, 0)
  }
})

test('a stalled request times out and leaves the snapshot readable', async () => {
  const h = client((_url, { signal }) => new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(Error('timeout')))))
  h.timers.get(1)()
  await h.done
  assert.equal(h.nodes['[data-github-weekly]'].textContent, 'saved weekly')
  assert.match(h.nodes['[data-github-refresh]'].textContent, /showing the saved snapshot/)
})

test('a stalled image gets a visible fallback and a late successful load restores it', async () => {
  const h = client(async () => ({ ok: false }), true)
  await h.done
  assert.equal(h.timers.size, 1)
  ;[...h.timers.values()][0]()
  assert.equal(h.img.hidden, true)
  assert.equal(h.fallback.hidden, false)
  h.events.load()
  assert.equal(h.img.hidden, false)
  assert.equal(h.fallback.hidden, true)
  assert.equal(h.timers.size, 0)
})
