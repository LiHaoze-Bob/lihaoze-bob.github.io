import assert from 'node:assert/strict'
import test from 'node:test'
import { parseFragment } from 'parse5'
import { highlightCodeBlocks } from '../src/lib/code.mjs'

const text = node => node.nodeName === '#text' ? node.value : (node.childNodes || []).map(text).join('')
const escape = source => source.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
const block = (language, source) => `<div class="note-code" data-language="${language}"><pre><code>${escape(source)}</code></pre></div>`

test('informal JSON and abbreviated HTTP retain exact text without error markup', () => {
  for (const [language, source, token] of [
    ['json', 'weather_tool = {"name": "get_weather", "enabled": true}\n', 'property'],
    ['json', 'response = client.chat.completions.create(model=model)\n', null],
    ['http', 'GET /weather?city=Pittsburgh&units=F\nX-API-Key: 调用者的密钥\n', 'header-name'],
    ['http', 'GET /weather HTTP/1.1\nHost: example.com\n', 'method'],
  ]) {
    const html = highlightCodeBlocks(block(language, source))
    assert.equal(text(parseFragment(html)), source)
    assert.doesNotMatch(html, /class="err"/)
    if (token) assert.match(html, new RegExp(`class="token ${token}`))
  }
})

test('code examples cannot create HTML elements and unknown languages remain readable', () => {
  for (const language of ['html', 'python', 'unknown-example', 'mermaid', 'plaintext', 'meta', 'constructor', 'extend']) {
    const source = '<img src="secret"> &amp; {{ literal }}\n\nx\u00a0y\t尾行\n'
    const html = highlightCodeBlocks(block(language, source))
    assert.equal(text(parseFragment(html)), source)
    assert.doesNotMatch(html, /<img\b/)
  }
})

test('nested blocks get independent grammars and inline code stays literal', () => {
  const inline = '<p><code>"literal" &amp; inline</code></p>'
  const html = highlightCodeBlocks(`<section>${inline}${block('json', '{"x": 1}')}${block('python', 'def hello(): pass')}</section>`)
  assert.ok(html.includes(inline))
  assert.match(html, /token property/)
  assert.match(html, /token keyword/)
})
