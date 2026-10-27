import { createHash } from 'node:crypto'
import { mkdir, writeFile } from 'node:fs/promises'
import { join } from 'node:path'
import { mathjax } from 'mathjax-full/js/mathjax.js'
import { TeX } from 'mathjax-full/js/input/tex.js'
import { AllPackages } from 'mathjax-full/js/input/tex/AllPackages.js'
import { SVG } from 'mathjax-full/js/output/svg.js'
import { liteAdaptor } from 'mathjax-full/js/adaptors/liteAdaptor.js'
import { RegisterHTMLHandler } from 'mathjax-full/js/handlers/html.js'
import sharp from 'sharp'

const adaptor = liteAdaptor()
RegisterHTMLHandler(adaptor)

export function createFeedMathRenderer(assetDirectory) {
  // Keep TeX definitions within an article, as they are on the website.
  const document = mathjax.document('', {
    InputJax: new TeX({ packages: AllPackages.filter(name =>
      !['autoload', 'require', 'noerrors', 'noundefined'].includes(name)) }),
    OutputJax: new SVG({ fontCache: 'none' })
  })
  const cache = new Map()
  return async (source, display) => {
    const container = document.convert(source, { display, em: 16, ex: 8, containerWidth: 720 })
    const svg = adaptor.firstChild(container)
    // Invalid TeX remains visible as literal text instead of becoming an error image.
    if (adaptor.outerHTML(svg).includes('data-mml-node="merror"')) return null
    const width = Math.max(1, Math.ceil(parseFloat(adaptor.getAttribute(svg, 'width')) * 8))
    const height = Math.max(1, Math.ceil(parseFloat(adaptor.getAttribute(svg, 'height')) * 8))
    adaptor.setAttribute(svg, 'width', width * 2)
    adaptor.setAttribute(svg, 'height', height * 2)
    adaptor.setAttribute(svg, 'color', '#111111')
    const rendered = adaptor.outerHTML(svg)
    const hash = createHash('sha256').update(`rss-math-v1:${display}:${rendered}`).digest('hex')
    if (cache.has(hash)) return cache.get(hash)
    const { data, info } = await sharp(Buffer.from(rendered))
      .flatten({ background: '#ffffff' })
      .extend({ top: 4, bottom: 4, left: 4, right: 4, background: '#ffffff' })
      .png().toBuffer({ resolveWithObject: true })
    await mkdir(assetDirectory, { recursive: true })
    const filename = `${hash}.png`
    await writeFile(join(assetDirectory, filename), data)
    const result = { filename, width: Math.ceil(info.width / 2), height: Math.ceil(info.height / 2) }
    cache.set(hash, result)
    return result
  }
}
