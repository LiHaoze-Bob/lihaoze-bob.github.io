import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { watchingCards } from '../src/lib/bangumi.mjs'

const entry = (id, updated_at, extra = {}) => ({
  subject_id: id, subject_type: 2, type: 3, private: false, updated_at,
  subject: { name: 'Original title', name_cn: `番剧 ${id}`, images: { common: 'https://lain.bgm.tv/pic/cover/example.jpg' } },
  ...extra
})

test('selects four most recently updated public anime being watched without mutating the source', () => {
  const data = [1, 2, 3, 4, 5].map(id => entry(id, `2026-11-0${id}T10:00:00+08:00`))
  data.push(entry(6, '2026-11-06', { private: true }), entry(7, '2026-11-07', { type: 2 }), entry(8, '2026-11-08', { subject_type: 1 }))
  assert.deepEqual(watchingCards({ data }).map(card => card.id), [5, 4, 3, 2])
  assert.equal(data[0].subject_id, 1)
})

test('uses original titles when needed, removes duplicate IDs, and excludes unsafe image URLs', () => {
  const original = entry(1, '2026-11-03', { subject: { name: 'Original title', images: { common: 'javascript:alert(1)' } } })
  assert.deepEqual(watchingCards({ data: [original, original] }), [{ id: 1, title: 'Original title', image: '', updatedAt: '2026-11-03' }])
})

test('distinguishes an empty collection from an invalid response', () => {
  assert.deepEqual(watchingCards({ data: [] }), [])
  for (const payload of [null, {}, { data: 'unavailable' }, { data: [entry(-1, '2026-11-03')] }]) assert.throws(() => watchingCards(payload))
})

class Element {
  constructor() { this.children = []; this.textContent = ''; this.hidden = false; this.complete = false }
  append(...nodes) { this.children.push(...nodes) }
  replaceChildren(...nodes) { this.children = nodes }
  setAttribute() {}
  addEventListener() {}
  querySelectorAll() { return [] }
}
function refresh(fetch) {
  const grid = new Element(), status = new Element(), empty = new Element()
  grid.children = ['saved cards']; status.textContent = 'Saved list · 2026-11-03'; empty.hidden = true
  const root = { dataset: { username: '1297862' }, querySelector: key => ({ '[data-bangumi-grid]': grid, '[data-bangumi-updated]': status, '[data-bangumi-empty]': empty })[key] }
  const exports = {}, timers = new Map()
  const compiled = ts.transpile(readFileSync(new URL('../src/scripts/bangumi.ts', import.meta.url), 'utf8'), { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 })
  vm.runInNewContext(compiled, { exports, require: () => ({ watchingCards }), document: { createElement: () => new Element() }, AbortController, fetch,
    setTimeout: fn => { timers.set(1, fn); return 1 }, clearTimeout: id => timers.delete(id) })
  return { grid, status, empty, timers, done: exports.setupBangumiWatching(root) }
}

test('live refresh replaces saved cards with public links and text, and handles an empty watchlist', async () => {
  const h = refresh(async () => ({ ok: true, json: async () => ({ data: [entry(123, '2026-11-03')] }) }))
  await h.done
  const link = h.grid.children[0].children[0]
  assert.equal(link.href, 'https://bgm.tv/subject/123')
  assert.equal(link.children[1].textContent, '番剧 123')
  assert.equal(h.empty.hidden, true)
  assert.equal(h.timers.size, 0)
  const empty = refresh(async () => ({ ok: true, json: async () => ({ data: [] }) }))
  await empty.done
  assert.equal(empty.grid.children.length, 0)
  assert.equal(empty.empty.hidden, false)
})

test('HTTP failures, malformed data and timeouts keep the dated saved list', async () => {
  for (const fetch of [async () => ({ ok: false }), async () => ({ ok: true, json: async () => ({ error: 'unavailable' }) })]) {
    const h = refresh(fetch)
    await h.done
    assert.deepEqual(h.grid.children, ['saved cards'])
    assert.match(h.status.textContent, /2026-11-03.*Update unavailable/)
  }
  const stalled = refresh((_url, { signal }) => new Promise((_resolve, reject) => signal.addEventListener('abort', () => reject(Error('timeout')))))
  stalled.timers.get(1)()
  await stalled.done
  assert.deepEqual(stalled.grid.children, ['saved cards'])
  assert.equal(stalled.timers.size, 0)
})
