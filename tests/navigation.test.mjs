import test from 'node:test'
import assert from 'node:assert/strict'
import { sectionFor, normalizeSection, displayDirectory, displayBreadcrumbs, paginateNotes, groupByYear } from '../src/lib/navigation.mjs'

test('legacy search links select the same content type as current links', () => {
  for (const [input, expected] of [['Course', 'Courses'], ['Tech', 'Articles'], ['Reading', 'Reading'], ['Articles', 'Articles'], ['', ''], ['unknown', '']]) {
    assert.equal(normalizeSection(input), expected)
  }
  assert.equal(sectionFor('knowledge/tools/IPA 自动续签').label, 'Articles')
  assert.equal(sectionFor('courses/ADS-ZJU/Dynamic Programming').label, 'Courses')
  assert.equal(sectionFor('reading/paper/Toolformer').label, 'Reading')
  assert.equal(sectionFor('knowledgeable/example'), undefined)
})

test('display paths hide only known storage folders and retain meaningful descendants', () => {
  assert.deepEqual(displayDirectory('knowledge/tech/AI/Example', ['Tech', '技术积累', '人工智能']), ['Articles', '人工智能'])
  assert.deepEqual(displayDirectory('knowledge/tools/Example', ['Tech', 'Tools']), ['Articles'])
  assert.deepEqual(displayDirectory('reading/paper/Example', ['Reading', 'Paper']), ['Reading'])
  assert.deepEqual(displayDirectory('reading/reading/Example', ['Reading', 'Reading']), ['Reading'])
  assert.deepEqual(displayDirectory('reading/reader/Example', ['Reading', 'Reader']), ['Reading', 'Reader'])
  assert.deepEqual(displayDirectory('courses/FDS/notes/Example', ['Course', 'FDS', 'notes']), ['Courses', 'FDS', 'notes'])
  const crumbs = [{ title: 'Tech', url: '/knowledge/' }, { title: '技术积累', url: '/knowledge/tech/' }, { title: '人工智能', url: '/knowledge/tech/AI/' }]
  assert.deepEqual(displayBreadcrumbs(crumbs), [{ title: 'Articles', url: '/knowledge/' }, { title: '人工智能', url: '/knowledge/tech/AI/' }])
  assert.equal(crumbs[0].title, 'Tech', 'raw metadata must not be mutated')
})

test('pagination keeps every note once at the zero, one, ten and eleven boundaries', () => {
  for (const size of [0, 1, 10, 11]) {
    const notes = Array.from({ length: size }, (_, index) => ({ url: `/note-${index}/` }))
    const first = paginateNotes(notes, 1)
    assert.equal(first.count, size > 10 ? 2 : 1)
    assert.equal(first.notes.length, Math.min(size, 10))
    const collected = Array.from({ length: first.count }, (_, index) => paginateNotes(notes, index + 1).notes).flat()
    assert.deepEqual(collected.map(note => note.url), notes.map(note => note.url))
  }
})

test('year headings use Shanghai dates after pagination without changing article order', () => {
  const notes = [
    { url: '/new/', publishedAt: '2026-12-31T16:30:00Z' },
    { url: '/old/', publishedAt: '2026-12-31T15:30:00Z' },
    ...Array.from({ length: 9 }, (_, index) => ({ url: `/older-${index}/`, publishedAt: '2026-01-01T00:00:00Z' }))
  ]
  const first = groupByYear(paginateNotes(notes, 1).notes)
  assert.deepEqual(first.map(group => group.year), ['2027', '2026'])
  assert.equal(first[0].notes[0].url, '/new/')
  assert.equal(first[1].notes.length, 9)
  assert.deepEqual(groupByYear(paginateNotes(notes, 2).notes).map(group => [group.year, group.notes.length]), [['2026', 1]])
  assert.deepEqual(groupByYear([]), [])
})
