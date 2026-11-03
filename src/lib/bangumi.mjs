/**
 * Keep only the public fields needed by the four Watching cards.
 * @returns {Array<{id: number, title: string, image: string, updatedAt: string}>}
 */
export function watchingCards(payload) {
  if (!payload || !Array.isArray(payload.data)) throw new Error('Invalid Bangumi collection')
  const seen = new Set()
  return payload.data.filter(item => item?.private === false && item.type === 3 && item.subject_type === 2)
    .map(item => {
      const title = (item.subject?.name_cn || item.subject?.name || '').trim()
      if (!Number.isSafeInteger(item.subject_id) || item.subject_id <= 0 || !title || !Number.isFinite(Date.parse(item.updated_at))) {
        throw new Error('Invalid Bangumi entry')
      }
      let image = ''
      try {
        const url = new URL(item.subject.images?.common || '')
        if (url.protocol === 'https:' && url.hostname === 'lain.bgm.tv') image = url.href
      } catch { /* A missing cover still has a readable title. */ }
      return { id: item.subject_id, title, image, updatedAt: item.updated_at }
    })
    .sort((a, b) => Date.parse(b.updatedAt) - Date.parse(a.updatedAt) || a.id - b.id)
    .filter(item => { if (seen.has(item.id)) return false; seen.add(item.id); return true })
    .slice(0, 4)
}
