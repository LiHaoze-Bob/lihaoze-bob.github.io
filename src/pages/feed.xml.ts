import rss from '@astrojs/rss'
import { notes } from '../lib/content'
import { feedContent } from '../lib/feed'
import { join } from 'node:path'

const site = 'https://lihaoze-bob.github.io'

export async function GET() {
  return rss({
    title: 'sychostar', description: '课程笔记、技术积累与阅读记录',
    site,
    customData: `<follow_challenge>
      <feedId>1349994631041386854</feedId>
      <userId>1349750604565746119</userId>
    </follow_challenge>`,
    items: await Promise.all(notes.map(async note => ({ title: note.title, pubDate: new Date(note.publishedAt!),
      description: note.description || note.cardHeadings?.join(' · ') || note.title,
      content: await feedContent(note.html, new URL(note.url, site).href,
        join(process.env.ASTRO_OUT_DIR || 'site', 'assets/rss-math')), link: note.url })))
  })
}
