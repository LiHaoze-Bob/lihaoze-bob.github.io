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
  const duration = obsidian.match(/Time @Obsidian\s*·\s*\*\*([\d\s.]+(?:hrs?|hours?|mins?|minutes?|secs?|seconds?)(?:[\d\s.]+(?:hrs?|hours?|mins?|minutes?|secs?|seconds?))*)\*\*\s+in the last 7 days/)
  const noActivity = /^(?:🔮\s*)?Time @Obsidian · No activity tracked in the last 7 days yet\.$/.test(obsidian)
  const weekly = block('waka').match(/^```(?:txt|text)?\s*\n([\s\S]+?)\n```$/)?.[1].trim()
  const period = weekly?.match(/^(\d{4}-\d{2}-\d{2}) - (\d{4}-\d{2}-\d{2}) \(Asia\/Shanghai\)$/m)
  if ((!duration && !noActivity) || !weekly || weekly.length > 8_000 || !period || !/^Total Time: [\d\w .]+$/m.test(weekly)) {
    throw new Error('Unrecognized activity report')
  }
  return {
    obsidian: duration ? `Time @Obsidian · ${duration[1].trim()} in the last 7 days` : 'Time @Obsidian · No activity tracked in the last 7 days yet.',
    weekly, periodStart: period[1], periodEnd: period[2]
  }
}
