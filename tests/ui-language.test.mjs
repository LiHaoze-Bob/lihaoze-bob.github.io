import assert from 'node:assert/strict'
import test from 'node:test'
import vm from 'node:vm'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { normalizeSection } from '../src/lib/navigation.mjs'

// Minimal DOM double for exercising production event handlers and rendered text.
class Element {
  constructor(text = '') { this.textContent = text; this.children = []; this.dataset = {}; this.attributes = {}; this.events = {}; this.nodes = {}; this.hidden = false; this.value = '' }
  querySelector(s) { return this.nodes[s] || null }
  querySelectorAll(s) { return this.nodes[s] || [] }
  append(...nodes) { this.children.push(...nodes) }
  replaceChildren(...nodes) { this.children = nodes; this.textContent = '' }
  setAttribute(k,v) { this.attributes[k] = v }
  addEventListener(k,fn) { this.events[k] = fn }
  focus() {}
}
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve() }
const text = n => typeof n === 'string' ? n : n.textContent + n.children.map(text).join('')

function searchHarness() {
  const root = new Element(); root.dataset.noteTitles = '[]'
  for (const key of ['#search-input','form','.search-clear','.search-status','.search-results','.search-more','.search-retry','.search-shortcut']) root.nodes[key] = new Element()
  root.nodes['.search-filters button'] = ['', 'Courses', 'Reading', 'Blog'].map(section => { const e = new Element(); e.dataset.section = section; return e })
  const location = { href: 'https://example.com/search/?q=树&section=Tech', origin: 'https://example.com' }
  const tasks = new Map(); let id = 0; let count = 1; let failed = false
  const engine = { options: async () => {}, search: async (_q, options) => {
    assert.equal(options.filters.section, 'Blog')
    if (failed) throw Error('offline')
    return { results: Array.from({length:count}, () => ({data:async () => ({url:'/knowledge/中文/',excerpt:'中文内容',meta:{title:'中文标题',directory:'Blog / 中文目录'}})})) }
  } }
  // Match Vite's build-time environment substitution; TypeScript lowers imports to require.
  const compiled = ts.transpile(readFileSync(new URL('../src/scripts/search.ts', import.meta.url),'utf8').replaceAll('import.meta.env.BASE_URL', "'/'"), {module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022})
  const exports = {}
  vm.runInNewContext(compiled,{exports,require:p => p.includes('navigation') ? {normalizeSection} : engine, URL, navigator:{platform:'MacIntel'},document:{createElement:()=>new Element()},window:{location,history:{replaceState:(_a,_b,url)=>location.href=String(url)},matchMedia:()=>({matches:false}),addEventListener(){}},setTimeout:fn=>{tasks.set(++id,fn);return id},clearTimeout:id=>tasks.delete(id)})
  exports.setupSearch(root)
  return { root, location, run:async () => {const pending=[...tasks.values()];tasks.clear();pending.forEach(fn=>fn());await flush()}, count:n=>count=n, fail:v=>failed=v }
}

test('English search handles loading, singular/plural, pagination and Chinese results with legacy filters',async () => {
  const h=searchHarness(), r=h.root
  assert.equal(r.nodes['.search-status'].textContent,'Searching…')
  assert.match(h.location.href,/section=Blog/)
  await h.run()
  assert.equal(r.nodes['.search-status'].textContent,'1 result')
  assert.match(text(r.nodes['.search-results']),/中文标题/)
  h.count(12);r.nodes['.search-retry'].events.click();await h.run()
  assert.equal(r.nodes['.search-status'].textContent,'12 results')
  assert.equal(r.nodes['.search-results'].children.length,10)
  r.nodes['.search-more'].events.click();await flush()
  assert.equal(r.nodes['.search-results'].children.length,12)
  assert.equal(r.nodes['.search-status'].textContent,'12 results')
  assert.equal(r.nodes['.search-more'].hidden,true)
})

test('English search handles empty results and recovery after a failed request',async () => {
  const h=searchHarness(),r=h.root;h.count(0);await h.run()
  assert.equal(r.nodes['.search-status'].textContent,'No results.')
  h.fail(true);r.nodes['.search-retry'].events.click();await h.run()
  assert.equal(r.nodes['.search-status'].textContent,'Search unavailable.')
  assert.equal(r.nodes['.search-retry'].hidden,false)
  h.fail(false);h.count(1);r.nodes['.search-retry'].events.click();await h.run()
  assert.equal(r.nodes['.search-status'].textContent,'1 result')
})

test('clearing a query returns to an empty search page', async () => {
  const h = searchHarness(), r = h.root
  await h.run()
  r.nodes['.search-clear'].events.click()
  assert.equal(r.nodes['#search-input'].value, '')
  assert.equal(r.nodes['.search-status'].textContent, '')
  assert.equal(r.nodes['.search-results'].hidden, true)
  assert.equal(r.nodes['.search-clear'].hidden, true)
  assert.equal(r.nodes['.search-more'].hidden, true)
  assert.ok(!new URL(h.location.href).searchParams.has('q'))
})

function steamHarness(lang='en', failed=false) {
  const card=new Element();card.dataset={steamEndpoint:'https://example.com/status',uiLang:lang}
  if (lang === null) delete card.dataset.uiLang
  for(const key of ['.steam-refresh','.steam-status','.steam-level','.steam-stats','.steam-playtime','.steam-recent','.steam-identity strong','.steam-status-updated time','.steam-stats-updated time'])card.nodes[key]=new Element()
  card.nodes['.steam-status'].textContent='Snapshot'
  const data={status:'in-game',updatedAt:new Date().toISOString(),name:'中文玩家',currentGame:'中文游戏',isPublic:true,stats:{updatedAt:new Date().toISOString(),level:3,badges:1,games:2,recentHours:4,recentGames:[{appid:'123',name:'中文游戏',hours:5}]}}
  vm.runInNewContext(readFileSync(new URL('../site-template/assets/js/steam.js',import.meta.url),'utf8'), {document:{querySelector:()=>card,createElement:()=>new Element(),hidden:false,addEventListener(){}},window:{addEventListener(){}},URL,Intl,Date,AbortController,fetch:async ()=>{if(failed)throw Error('offline');return {ok:true,json:async()=>data}},setTimeout:()=>1,clearTimeout(){},setInterval(){},clearInterval(){}})
  return card
}

test('Steam English live rendering preserves content and statistics',async () => {
  const card=steamHarness()
  assert.equal(card.nodes['.steam-refresh'].textContent,'Updating…')
  await flush()
  assert.equal(card.nodes['.steam-status'].textContent,'Playing 中文游戏')
  assert.equal(text(card.nodes['.steam-stats']),'Badges1Games2')
  assert.equal(text(card.nodes['.steam-playtime']),'Past two weeks: 4 hours')
  assert.match(text(card.nodes['.steam-recent']),/中文游戏5 h total/)
  assert.equal(card.nodes['.steam-refresh'].textContent,'Updates every 60 seconds')
})

test('Steam failure keeps previous data with English status; legacy default remains Chinese',async () => {
  const english=steamHarness('en',true)
  await flush()
  assert.equal(english.nodes['.steam-status'].textContent,'Snapshot')
  assert.equal(english.nodes['.steam-refresh'].textContent,'Update unavailable; showing previous data')
  // Explicitly absent language is the Chirpy compatibility path.
  const chinese=steamHarness(null);await flush()
  assert.equal(chinese.nodes['.steam-status'].textContent,'正在玩 中文游戏')
})
