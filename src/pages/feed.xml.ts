import rss from '@astrojs/rss'
import { notes } from '../lib/content'
import { feedContent } from '../lib/feed'

const site = 'https://lihaoze-bob.github.io'

export function GET() {
  return rss({
    title: 'sychostar', description: '课程笔记、技术积累与阅读记录',
    site,
    items: notes.map(note => ({ title: note.title, pubDate: new Date(note.publishedAt!),
      description: note.description || note.cardHeadings?.join(' · ') || note.title,
      content: feedContent(note.html, new URL(note.url, site).href), link: note.url }))
  })
}
