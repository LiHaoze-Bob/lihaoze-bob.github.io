import { readFileSync } from 'node:fs'

export interface NotePage {
  route: string
  url: string
  title: string
  subtitle?: string
  html: string
  description?: string
  headings: { depth: number; slug: string; text: string }[]
  breadcrumbs: { title: string; subtitle?: string; url: string }[]
  directory?: string[]
  cardHeadings?: string[]
  publishedAt?: string
  updatedAt?: string
  tags?: string[] | string
  tagLinks?: { title: string; url: string }[]
  isNote: boolean
  folder_previous?: { title: string; subtitle?: string; url: string } | null
  folder_next?: { title: string; subtitle?: string; url: string } | null
}

const data = JSON.parse(readFileSync(process.env.ASTRO_CONTENT_FILE || '.runtime/astro-content.json', 'utf8'))
export const pages: NotePage[] = data.pages
export const notes = pages.filter(page => page.isNote).sort((a, b) =>
  Date.parse(b.publishedAt || '') - Date.parse(a.publishedAt || '') || a.route.localeCompare(b.route))

export function collectTags(articles: NotePage[]) {
  const tags = new Map<string, { title: string; url: string; count: number }>()
  for (const note of articles) {
    const seen = new Set<string>()
    for (const tag of note.tagLinks || []) {
      if (seen.has(tag.url)) continue
      seen.add(tag.url)
      const entry = tags.get(tag.url)
      if (entry) entry.count++
      else tags.set(tag.url, { ...tag, count: 1 })
    }
  }
  return [...tags.values()].sort((a, b) => b.count - a.count || a.title.localeCompare(b.title, 'zh-CN'))
}

export const date = (value: string) => new Intl.DateTimeFormat('en-US', {
  month: 'short', day: 'numeric', year: 'numeric', timeZone: 'Asia/Shanghai'
}).format(new Date(value))
