/** Read only the public activity blocks; never render README HTML. */
export function parseGitHubActivity(readme) {
  if (typeof readme !== 'string' || readme.length > 100_000) throw new Error('Invalid profile README')
  const block = name => {
    const start = `<!--START_SECTION:${name}-->`
    const end = `<!--END_SECTION:${name}-->`
    const from = readme.indexOf(start)
    const to = readme.indexOf(end, from + start.length)
    if (from < 0 || to < 0) throw new Error(`Missing ${name} report`)
    return readme.slice(from + start.length, to).trim()
  }
  const obsidian = block('obsidian')
  const sourceUpdatedAt = obsidian.match(/<!-- activity-updated-at: (.*?) -->/)?.[1]
  if (sourceUpdatedAt !== undefined && (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(sourceUpdatedAt) ||
      !Number.isFinite(Date.parse(sourceUpdatedAt)) || new Date(sourceUpdatedAt).toISOString() !== sourceUpdatedAt.replace('Z', '.000Z'))) {
    throw new Error('Invalid activity timestamp')
  }
  const duration = obsidian.match(/Time @Obsidian\s*·\s*\*\*([\d\s.]+(?:hrs?|hours?|mins?|minutes?|secs?|seconds?)(?:[\d\s.]+(?:hrs?|hours?|mins?|minutes?|secs?|seconds?))*)\*\*\s+in the last 7 days/)
  const noActivity = /^(?:🔮\s*)?Time @Obsidian · No activity tracked in the last 7 days yet\.$/m.test(obsidian)
  const weekly = block('waka').match(/^```(?:txt|text)?\s*\n([\s\S]+?)\n```$/)?.[1].trim()
  const period = weekly?.match(/^(\d{4}-\d{2}-\d{2}) - (\d{4}-\d{2}-\d{2}) \(Asia\/Shanghai\)$/m)
  if ((!duration && !noActivity) || !weekly || weekly.length > 8_000 || !period || !/^Total Time: [\d\w .]+$/m.test(weekly)) {
    throw new Error('Unrecognized activity report')
  }
  return {
    obsidian: duration ? `Time @Obsidian · ${duration[1].trim()} in the last 7 days` : 'Time @Obsidian · No activity tracked in the last 7 days yet.',
    weekly, periodStart: period[1], periodEnd: period[2],
    ...(sourceUpdatedAt ? { sourceUpdatedAt } : {})
  }
}

export function formatActivityUpdatedAt(timestamp) {
  const time = new Date(timestamp).toLocaleString('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit'
  })
  return `Updated ${time} (Asia/Shanghai) · refreshes hourly`
}
