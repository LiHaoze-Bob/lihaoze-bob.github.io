import { parseFragment, serialize, type DefaultTreeAdapterMap } from 'parse5'

// Feed readers do not load the site's scripts or have its origin for relative URLs.
export function feedContent(html: string, articleUrl: string): string {
  const fragment = parseFragment(html)
  function visit(parent: DefaultTreeAdapterMap['parentNode']) {
    parent.childNodes = parent.childNodes.filter(node =>
      !('tagName' in node && ['script', 'style', 'link', 'button'].includes(node.tagName)))
    for (const node of parent.childNodes) {
      if (!('tagName' in node)) continue
      for (const attribute of node.attrs) {
        if (['href', 'src', 'poster'].includes(attribute.name)) {
          attribute.value = new URL(attribute.value, articleUrl).href
        }
      }
      // Keep folded callouts readable even in clients without disclosure controls.
      if (node.tagName === 'details' && !node.attrs.some(attr => attr.name === 'open')) {
        node.attrs.push({ name: 'open', value: '' })
      }
      visit(node)
    }
  }
  visit(fragment)
  return serialize(fragment)
}
