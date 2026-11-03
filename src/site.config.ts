import type { Config, IntegrationUserConfig, ThemeUserConfig } from 'astro-pure/types'
import { profile } from './data/profile'

export const base = ''
export const href = (path: string) => base + (path.startsWith('/') ? path : '/' + path)

export const comments = {
  enable: true,
  repo: 'LiHaoze-Bob/lihaoze-bob.github.io',
  repoId: 'R_kgDOUaolUQ',
  category: 'Announcements',
  categoryId: 'DIC_kwDOUaolUc4DG49S'
}

export const theme: ThemeUserConfig = {
  title: profile.nickname,
  author: 'sychostar',
  description: 'Haoze Li (sychostar) — projects, course notes, reading, and articles.',
  favicon: href('/assets/images/avatar.png'),
  socialCard: href('/assets/images/avatar.png'),
  locale: {
    lang: 'en', attrs: 'en_US', dateLocale: 'en-US',
    dateOptions: { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'Asia/Shanghai' }
  },
  logo: { src: href('/assets/images/avatar.png'), alt: 'sychostar' },
  titleDelimiter: '•',
  prerender: true,
  npmCDN: 'https://cdn.jsdelivr.net/npm',
  head: [], customCss: [],
  header: {
    menu: [
      { title: 'Notes', link: href('/notes/') },
      { title: 'Projects', link: href('/projects/') },
      { title: 'About', link: href('/about/') }
    ]
  },
  footer: {
    year: `© ${new Date().getFullYear()} `, links: [], credits: false,
    social: [
      { icon: 'github', label: 'GitHub', href: 'https://github.com/LiHaoze-Bob' },
      { icon: 'rss', label: 'RSS', href: href('/feed.xml') }
    ]
  },
  content: { externalLinks: { content: ' ↗', properties: {} }, blogPageSize: 10, share: [] }
}

export const integ: IntegrationUserConfig = {
  links: { logbook: [], applyTip: [], cacheAvatar: false },
  pagefind: true,
  quote: { server: '', target: '' },
  typography: { class: 'prose text-base', blockquoteStyle: 'normal', inlineCodeBlockStyle: 'modern' },
  mediumZoom: { enable: true, selector: '#content img.zoomable', options: {} },
  waline: { enable: false, showMeta: false, additionalConfigs: {} }
}

export default { ...theme, integ } as Config
