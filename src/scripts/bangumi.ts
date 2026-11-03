import { watchingCards } from '../lib/bangumi.mjs'

export async function setupBangumiWatching(root: HTMLElement) {
  const grid = root.querySelector<HTMLElement>('[data-bangumi-grid]')!
  const status = root.querySelector<HTMLElement>('[data-bangumi-updated]')!
  const empty = root.querySelector<HTMLElement>('[data-bangumi-empty]')!
  const savedStatus = status.textContent
  const watchCover = (img: HTMLImageElement) => {
    img.addEventListener('error', () => { img.hidden = true }, { once: true })
    if (img.complete && !img.naturalWidth) img.hidden = true
  }
  grid.querySelectorAll('img').forEach(watchCover)
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    const username = encodeURIComponent(root.dataset.username || '')
    const response = await fetch(`https://api.bgm.tv/v0/users/${username}/collections?subject_type=2&type=3&limit=50`, { signal: controller.signal, credentials: 'omit' })
    if (!response.ok) throw new Error('Bangumi is unavailable')
    const cards = watchingCards(await response.json())
    const items = cards.map(card => {
      const item = document.createElement('li')
      const link = document.createElement('a')
      link.className = 'bangumi-card'
      link.href = `https://bgm.tv/subject/${card.id}`
      const poster = document.createElement('div')
      poster.className = 'bangumi-poster'
      const placeholder = document.createElement('span')
      placeholder.className = 'bangumi-cover-fallback'
      placeholder.textContent = 'BGM'
      placeholder.setAttribute('aria-hidden', 'true')
      poster.append(placeholder)
      if (card.image) {
        const img = document.createElement('img')
        img.alt = ''; img.width = 240; img.height = 340
        img.loading = 'lazy'; img.decoding = 'async'; img.referrerPolicy = 'no-referrer'
        img.src = card.image
        watchCover(img)
        poster.append(img)
      }
      const badge = document.createElement('span')
      badge.className = 'bangumi-badge'
      const dot = document.createElement('span')
      dot.setAttribute('aria-hidden', 'true')
      badge.append(dot, 'Watching')
      poster.append(badge)
      const title = document.createElement('span')
      title.className = 'bangumi-title'; title.textContent = card.title
      link.append(poster, title); item.append(link)
      return item
    })
    grid.replaceChildren(...items)
    empty.hidden = cards.length > 0
    status.textContent = 'From my public Bangumi watchlist'
  } catch {
    status.textContent = `${savedStatus} · Update unavailable`
  } finally {
    clearTimeout(timeout)
  }
}
