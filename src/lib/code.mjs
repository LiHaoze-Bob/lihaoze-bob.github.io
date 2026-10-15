import Prism from 'prismjs'
import loadLanguages from 'prismjs/components/index.js'
import components from 'prismjs/components.js'
import { parseFragment, serialize } from 'parse5'

// Match Obsidian's reading view with Prism, without interpreting examples as
// syntax errors. Unknown languages and diagrams stay escaped plain text.
loadLanguages.silent = true
const supportedLanguages = new Set(Object.entries(components.languages)
  .filter(([id]) => id !== 'meta')
  .flatMap(([id, definition]) => [id, ...[definition.alias || []].flat()]))

// Prism.util.encode replaces nonbreaking spaces. Keep them in copied literals.
function encode(tokens) {
  if (typeof tokens === 'string') return tokens.replaceAll('&', '&amp;').replaceAll('<', '&lt;')
  if (Array.isArray(tokens)) return tokens.map(encode)
  return new Prism.Token(tokens.type, encode(tokens.content), tokens.alias)
}

function highlight(source, grammar, language) {
  if (!grammar) return encode(source)
  const env = { code: source, grammar, language }
  Prism.hooks.run('before-tokenize', env)
  env.tokens = Prism.tokenize(env.code, env.grammar)
  Prism.hooks.run('after-tokenize', env)
  return Prism.Token.stringify(encode(env.tokens), env.language)
}

const attr = (node, name) => node.attrs?.find(attribute => attribute.name === name)?.value
const text = node => node.nodeName === '#text'
  ? node.value
  : (node.childNodes || []).map(text).join('')

export function highlightCodeBlocks(html) {
  if (!html.includes('class="note-code"')) return html
  const fragment = parseFragment(html)
  function visit(node, language) {
    if (attr(node, 'class')?.split(/\s+/).includes('note-code')) {
      language = (attr(node, 'data-language') || 'plaintext').toLowerCase()
    }
    if (node.tagName === 'code' && language) {
      const supported = supportedLanguages.has(language)
      if (supported && !Object.hasOwn(Prism.languages, language)) loadLanguages([language])
      const source = text(node)
      const grammar = supported ? Prism.languages[language] : undefined
      const highlighted = highlight(source, grammar, language)
      node.childNodes = parseFragment(highlighted).childNodes
      for (const child of node.childNodes) child.parentNode = node
      return
    }
    for (const child of node.childNodes || []) visit(child, language)
  }
  visit(fragment)
  return serialize(fragment)
}
