interface SearchData {
  url: string
  excerpt: string
  meta: { title?: string; directory?: string }
  sub_results?: { title: string; url: string }[]
}
interface SearchResult { data: () => Promise<SearchData> }
interface SearchEngine {
  options: (options: { baseUrl: string; excerptLength: number }) => Promise<void>
  search: (query: string, options: { filters: Record<string, string> }) => Promise<{ results: SearchResult[] }>
}

export function setupSearch(root: HTMLElement) {
  const input = root.querySelector<HTMLInputElement>('#search-input')!
  const form = root.querySelector<HTMLFormElement>('form')!
  const clear = root.querySelector<HTMLButtonElement>('.search-clear')!
  const filters = [...root.querySelectorAll<HTMLButtonElement>('.search-filters button')]
  const status = root.querySelector<HTMLElement>('.search-status')!
  const results = root.querySelector<HTMLUListElement>('.search-results')!
  const more = root.querySelector<HTMLButtonElement>('.search-more')!
  const retry = root.querySelector<HTMLButtonElement>('.search-retry')!
  const recent = root.querySelector<HTMLElement>('.search-recent')!
  const shortcut = root.querySelector<HTMLElement>('.search-shortcut')!
  const entries: { url: string; title: string; subtitle?: string }[] = JSON.parse(root.dataset.noteTitles || '[]')
  const path = (url: string) => new URL(url, window.location.origin).pathname.replace(/\/$/, '')
  const titles = new Map(entries.map(entry => [path(entry.url), entry]))
  const pageSize = 10
  let section = ''
  let timer: ReturnType<typeof setTimeout>
  let version = 0
  let composing = false
  let matches: SearchResult[] = []
  let displayed = 0
  let enginePromise: Promise<SearchEngine> | undefined
  let loadAttempt = 0

  shortcut.textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘ K' : 'Ctrl K'

  function loadEngine() {
    if (!enginePromise) {
      const path = `${import.meta.env.BASE_URL.replace(/\/$/, '')}/pagefind/pagefind.js`
      const url = loadAttempt++ ? `${path}?retry=${loadAttempt}` : path
      enginePromise = import(/* @vite-ignore */ url).then(async (engine: SearchEngine) => {
        await engine.options({ baseUrl: `${import.meta.env.BASE_URL.replace(/\/$/, '')}/`, excerptLength: 28 })
        return engine
      }).catch(error => { enginePromise = undefined; throw error })
    }
    return enginePromise
  }

  function updateURL() {
    const url = new URL(window.location.href)
    const query = input.value.trim()
    if (query) url.searchParams.set('q', query)
    else url.searchParams.delete('q')
    if (section) url.searchParams.set('section', section)
    else url.searchParams.delete('section')
    window.history.replaceState(null, '', url)
  }

  function updateFilters() {
    filters.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.section === section)))
    let visible = 0
    recent.querySelectorAll<HTMLElement>('li').forEach(item => {
      item.hidden = (!!section && item.dataset.section !== section) || visible >= 8
      if (!item.hidden) visible++
    })
    recent.querySelector<HTMLElement>('.search-recent-empty')!.hidden = visible > 0
  }

  function reset() {
    results.replaceChildren()
    results.hidden = true
    results.setAttribute('aria-busy', 'false')
    more.hidden = true
    more.disabled = false
    retry.hidden = true
    matches = []
    displayed = 0
  }

  function showError() {
    // Pagefind caches rejected fragment/index promises. Retry with a fresh module.
    enginePromise = undefined
    status.textContent = '搜索暂时无法加载，请检查网络后重试。'
    retry.hidden = false
    more.hidden = true
    results.setAttribute('aria-busy', 'false')
  }

  function resultCard(data: SearchData) {
    const item = document.createElement('li')
    item.className = 'search-result'
    const directory = document.createElement('p')
    directory.className = 'search-result-directory'
    directory.textContent = data.meta.directory || '公开笔记'
    const heading = document.createElement('h2')
    const link = document.createElement('a')
    link.className = 'search-result-title search-note-link'
    link.href = data.url
    const entry = titles.get(path(data.url))
    const primary = document.createElement('span')
    primary.className = 'note-title-primary'
    primary.textContent = entry?.title || data.meta.title || '未命名笔记'
    link.append(primary)
    if (entry?.subtitle && entry.subtitle !== entry.title) {
      const secondary = document.createElement('span')
      secondary.className = 'note-title-secondary'
      secondary.textContent = entry.subtitle
      link.append(secondary)
    }
    heading.append(link)
    const excerpt = document.createElement('p')
    excerpt.className = 'search-result-excerpt'
    // Pagefind escapes content before adding its own <mark> elements.
    excerpt.innerHTML = data.excerpt
    item.append(directory, heading, excerpt)
    const anchors = data.sub_results?.filter(result => result.url.includes('#')).slice(0, 2) || []
    if (anchors.length) {
      const links = document.createElement('div')
      links.className = 'search-result-sections'
      anchors.forEach(result => {
        const anchor = document.createElement('a')
        anchor.href = result.url
        anchor.textContent = `↳ ${result.title}`
        links.append(anchor)
      })
      item.append(links)
    }
    return item
  }

  async function showMore(current: number, focusNew = false) {
    more.disabled = true
    results.setAttribute('aria-busy', 'true')
    try {
      const batch = await Promise.all(matches.slice(displayed, displayed + pageSize).map(match => match.data()))
      if (current !== version) return
      const cards = batch.map(resultCard)
      results.append(...cards)
      displayed += batch.length
      results.hidden = false
      results.setAttribute('aria-busy', 'false')
      more.hidden = displayed >= matches.length
      more.disabled = false
      status.textContent = `找到 ${matches.length} 篇笔记${more.hidden ? '' : `，已显示 ${displayed} 篇`}`
      if (focusNew) cards[0]?.querySelector<HTMLAnchorElement>('a')?.focus()
    } catch {
      if (current === version) showError()
    }
  }

  async function search(current: number) {
    const query = input.value.trim()
    try {
      const engine = await loadEngine()
      if (current !== version) return
      const response = await engine.search(query, { filters: { kind: 'note', ...(section ? { section } : {}) } })
      if (current !== version) return
      matches = response.results
      if (!matches.length) {
        status.textContent = `没有找到「${query}」${section ? `在 ${section} 栏目中` : ''}的相关笔记。试试更短的关键词${section ? '，或切换到「全部」' : ''}。`
        results.setAttribute('aria-busy', 'false')
        return
      }
      await showMore(current)
    } catch {
      if (current === version) showError()
    }
  }

  function schedule(immediate = false) {
    clearTimeout(timer)
    const current = ++version
    reset()
    const query = input.value.trim()
    clear.hidden = !input.value
    shortcut.hidden = !!input.value
    recent.hidden = !!query
    updateURL()
    if (!query) {
      status.textContent = ''
      return
    }
    status.textContent = '正在搜索…'
    results.setAttribute('aria-busy', 'true')
    timer = setTimeout(() => { void search(current) }, immediate ? 0 : 180)
  }

  function restoreURL() {
    const parameters = new URL(window.location.href).searchParams
    input.value = parameters.get('q') || ''
    const selected = parameters.get('section') || ''
    section = filters.some(button => button.dataset.section === selected) ? selected : ''
    updateFilters()
    schedule(true)
  }

  input.addEventListener('compositionstart', () => {
    composing = true
    clearTimeout(timer)
    version++
  })
  input.addEventListener('compositionend', () => { composing = false; schedule() })
  input.addEventListener('input', () => { if (!composing) schedule() })
  form.addEventListener('submit', event => { event.preventDefault(); if (!composing) schedule(true) })
  filters.forEach(button => button.addEventListener('click', () => {
    section = button.dataset.section || ''
    updateFilters()
    if (!composing) schedule(true)
  }))
  clear.addEventListener('click', () => { input.value = ''; schedule(true); input.focus() })
  retry.addEventListener('click', () => schedule(true))
  more.addEventListener('click', () => { void showMore(version, true) })
  root.addEventListener('keydown', event => {
    if (event.isComposing || composing || event.ctrlKey || event.metaKey || event.altKey) return
    if (event.key === 'Escape') {
      event.preventDefault()
      input.value = ''
      schedule(true)
      input.focus()
    }
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return
    const links = [...results.querySelectorAll<HTMLAnchorElement>('a')]
    const current = links.indexOf(document.activeElement as HTMLAnchorElement)
    if (document.activeElement !== input && current < 0) return
    if (!links.length) return
    event.preventDefault()
    if (document.activeElement === input) (event.key === 'ArrowDown' ? links[0] : links.at(-1))?.focus()
    else if (event.key === 'ArrowUp' && current === 0) input.focus()
    else links[(current + (event.key === 'ArrowDown' ? 1 : -1) + links.length) % links.length]?.focus()
  })
  window.addEventListener('popstate', restoreURL)
  restoreURL()
  if (window.matchMedia('(pointer: fine)').matches) input.focus({ preventScroll: true })
}
