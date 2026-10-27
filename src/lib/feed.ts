import { parseFragment, serialize, type DefaultTreeAdapterMap } from 'parse5'
import { createFeedMathRenderer } from './feed-math.mjs'

type Element = DefaultTreeAdapterMap['element']
const hasClass = (node: Element, name: string) => node.attrs.some(attr =>
  attr.name === 'class' && attr.value.split(/\s+/).includes(name))
const textContent = (node: DefaultTreeAdapterMap['node']): string =>
  node.nodeName === '#text' && 'value' in node ? node.value
    : 'childNodes' in node ? node.childNodes.map(textContent).join('') : ''
const element = (html: string) => parseFragment(html).childNodes[0] as Element
const replaceChildren = (parent: Element, children: DefaultTreeAdapterMap['childNode'][]) => {
  parent.childNodes = children
  for (const child of children) child.parentNode = parent
}

// Feed readers do not load the site's scripts or have its origin for relative URLs.
export async function feedContent(html: string, articleUrl: string, assetDirectory: string): Promise<string> {
  const fragment = parseFragment(html)
  const renderMath = createFeedMathRenderer(assetDirectory)
  async function visit(parent: DefaultTreeAdapterMap['parentNode']) {
    parent.childNodes = parent.childNodes.filter(node =>
      !('tagName' in node && ['script', 'style', 'link', 'button'].includes(node.tagName)))
    for (const node of parent.childNodes) {
      if (!('tagName' in node)) continue
      if (hasClass(node, 'obsidian-callout') || node.tagName === 'details') {
        // Semantic quotes survive readers stripping CSS and disclosure controls.
        node.tagName = node.nodeName = 'blockquote'
        node.attrs = node.attrs.filter(attr => attr.name === 'id')
        const title = node.childNodes.find((child): child is Element =>
          'tagName' in child && (hasClass(child, 'callout-title') || child.tagName === 'summary'))
        if (title) {
          const label = title.childNodes.find((child): child is Element =>
            'tagName' in child && hasClass(child, 'callout-title-inner'))
          const strong = element('<strong></strong>')
          replaceChildren(strong, [...(label || title).childNodes])
          title.tagName = title.nodeName = 'p'
          title.attrs = []
          replaceChildren(title, [strong])
        }
      }
      if (hasClass(node, 'arithmatex')) {
        const raw = textContent(node).trim()
        const source = raw.slice(2, -2).trim()
        const display = raw.startsWith('\\[')
        const image = await renderMath(source, display)
        const replacement = element(image ? '<img>' : '<code></code>')
        if (image) {
          replacement.attrs = Object.entries({
            src: new URL(`/assets/rss-math/${image.filename}`, articleUrl).href,
            alt: source, width: String(image.width), height: String(image.height)
          }).map(([name, value]) => ({ name, value }))
        } else {
          replaceChildren(replacement, [{ nodeName: '#text', value: raw, parentNode: replacement }])
        }
        node.attrs = node.attrs.filter(attr => attr.name !== 'class')
        replaceChildren(node, [replacement])
      }
      for (const attribute of node.attrs) {
        if (['href', 'src', 'poster'].includes(attribute.name)) {
          attribute.value = new URL(attribute.value, articleUrl).href
        }
      }
      await visit(node)
    }
  }
  await visit(fragment)
  return serialize(fragment)
}
