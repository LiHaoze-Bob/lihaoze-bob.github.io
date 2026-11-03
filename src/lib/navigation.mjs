import sections from '../data/sections.json' with { type: 'json' }

export { sections }

/** @param {string} route */
export function sectionFor(route) {
  return sections.find(section => section.route === route.split('/')[0])
}

/** @param {string} value */
export function normalizeSection(value) {
  return sections.find(section => section.label === value || section.legacyLabel === value)?.label || ''
}

/** @param {string} route @param {string[]} [directory] */
export function displayDirectory(route, directory = []) {
  const section = sectionFor(route)
  if (!section || !directory.length) return [...directory]
  const result = [section.label, ...directory.slice(1)]
  if (section.storageFolders.includes(route.split('/')[1])) result.splice(1, 1)
  return result
}

/** @template {{title: string, url: string}} T @param {T[]} crumbs @returns {T[]} */
export function displayBreadcrumbs(crumbs) {
  return crumbs.flatMap(crumb => {
    const parts = crumb.url.split('/').filter(Boolean)
    const section = sectionFor(parts[0] || '')
    if (!section) return [{ ...crumb }]
    if (parts.length === 2 && section.storageFolders.includes(parts[1])) return []
    return [{ ...crumb, title: parts.length === 1 ? section.label : crumb.title }]
  })
}

/** @template T @param {T[]} notes @param {number} [current] */
export function paginateNotes(notes, current = 1) {
  return { notes: notes.slice((current - 1) * 10, current * 10), count: Math.max(1, Math.ceil(notes.length / 10)) }
}

const yearFormat = new Intl.DateTimeFormat('en-US', { year: 'numeric', timeZone: 'Asia/Shanghai' })

/** @template {{publishedAt?: string}} T @param {T[]} notes */
export function groupByYear(notes) {
  /** @type {Map<string, T[]>} */
  const groups = new Map()
  for (const note of notes) {
    const year = note.publishedAt ? yearFormat.format(new Date(note.publishedAt)) : 'Undated'
    if (!groups.has(year)) groups.set(year, [])
    groups.get(year)?.push(note)
  }
  return Array.from(groups, ([year, notes]) => ({ year, notes }))
}
