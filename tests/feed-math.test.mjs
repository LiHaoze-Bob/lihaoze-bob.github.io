import assert from 'node:assert/strict'
import test from 'node:test'
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import sharp from 'sharp'
import { createFeedMathRenderer } from '../src/lib/feed-math.mjs'

test('RSS formulas produce visible self-hosted PNGs at twice their display resolution', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'rss-math-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const render = createFeedMathRenderer(directory)
  for (const [source, display] of [
    ['x^2', false],
    ['\\frac{1}{2}', true],
    ['\\begin{aligned}a &= b + c \\\\ d &= e\\end{aligned}', true]
  ]) {
    const result = await render(source, display)
    assert.ok(result)
    const image = sharp(await readFile(join(directory, result.filename)))
    const metadata = await image.metadata()
    assert.equal(metadata.format, 'png')
    assert.equal(Math.ceil(metadata.width / 2), result.width)
    assert.equal(Math.ceil(metadata.height / 2), result.height)
    const stats = await image.stats()
    assert.ok(stats.channels[0].min < 50, 'formula must contain visible dark pixels')
    assert.equal(stats.channels[0].max, 255, 'white background keeps formulas visible in dark readers')
    assert.deepEqual(await render(source, display), result)
  }
  assert.equal((await readdir(directory)).length, 3)
})

test('invalid TeX falls back to readable source rather than a missing formula image', async () => {
  const render = createFeedMathRenderer(join(tmpdir(), 'unused-rss-math'))
  assert.equal(await render('\\notARealCommand{x}', false), null)
})

test('article-local TeX macros cannot overwrite another formula or reuse a stale image', async t => {
  const directory = await mkdtemp(join(tmpdir(), 'rss-macros-'))
  t.after(() => rm(directory, { recursive: true, force: true }))
  const first = createFeedMathRenderer(directory)
  const second = createFeedMathRenderer(directory)
  await first('\\newcommand{\\foo}{x}\\foo', false)
  await second('\\newcommand{\\foo}{xxxxxxxx}\\foo', false)
  const short = await first('\\foo', false)
  const long = await second('\\foo', false)
  assert.notEqual(short.filename, long.filename)
  assert.ok(long.width > short.width)
  await first('\\renewcommand{\\foo}{xxxxxxxx}\\foo', false)
  const redefined = await first('\\foo', false)
  assert.equal(redefined.filename, long.filename)
  assert.equal(redefined.width, long.width)
})
